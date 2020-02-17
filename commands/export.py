# -*- coding: utf-8 -*-
import csv
import hashlib
import json
import logging
import re
import time
from io import StringIO, BytesIO

import boto3
import lxml.etree
import lxml.html
import requests
from botocore.exceptions import ClientError
from slugify import slugify
from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import ConversationHandler

import constants
from config import *
from helpers import lxml_stringify_children
from links import LINKS
from smartcat.api import SmartCAT, SmartcatException
from strings import *

logger = logging.getLogger(__name__)


def export_start(update, context):
    update.message.reply_text(ENTER_THE_DOCUMENT_NAME_ID_OR_CANCEL,
                              reply_markup=ReplyKeyboardRemove())
    return constants.STATE_EXPORT_CHOOSE_FORMAT


def export_choose_format(update, context):
    name_or_id = update.message.text.lower().strip()
    logger.info('Export request: {0}'.format(name_or_id))

    sc_api = SmartCAT(SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    try:
        document = sc_api.project.get_document_by_name(SMARTCAT_PROJECT_ID, name_or_id)
    except SmartcatException as e:
        logger.error('Error getting document: {0} {1}'.format(e.code, e.message))
        update.message.reply_text(SHIT_HAPPENS)
        return ConversationHandler.END

    if not document:
        logger.warning('Document not found')
        update.message.reply_text(NOTHING_FOUND)
        return ConversationHandler.END

    logger.info('Document id: {0}'.format(document['id']))
    context.user_data['document'] = document

    reply = "\nВ каком формате?"
    reply_keyboard = [[
        EXPORT_FORMAT_ORIGINAL_TEXT,
        EXPORT_FORMAT_TRANSLATION_TEXT,
        EXPORT_FORMAT_PONY_HTML,
        '/cancel',
    ]]
    update.message.reply_text(reply, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return constants.STATE_EXPORT


def export(update, context):
    """Export a document on /export command"""
    document = context.user_data['document']
    document_format = update.message.text.lower().strip()
    sc_api = SmartCAT(SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    response = sc_api.document.request_export(document['id'], target_type='multilangCsv')
    if response.status_code != 200:
        logger.error('Error requesting document export: code {0}'.format(response.status_code))
        update.message.reply_text(SHIT_HAPPENS)
        return ConversationHandler.END

    data = json.loads(response.content.decode('utf-8'))
    if not data or not data['id']:
        logger.error('Error requesting document export: invalid content')
        update.message.reply_text(SHIT_HAPPENS)
        return ConversationHandler.END

    task_id = data['id']
    logger.info('Export task id: {0}'.format(task_id))

    # now wait for the task to complete and get the document text

    document_text_original = ''
    document_text_translation = ''
    paragraphs_original = []
    paragraphs_translation = []
    tries = 1
    while tries < 10:
        time.sleep(tries * tries)
        response = sc_api.document.download_export_result(task_id)
        if response.status_code == 204:
            logger.info('Document not ready yet, retrying...')
            tries += 1
        else:
            if response.status_code == 200:
                f = StringIO(response.content.decode('utf-8'))
                reader = csv.reader(f, delimiter=',')
                next(reader)  # skip header
                for row in reader:
                    try:
                        document_text_original += row[0].strip() + "\n"
                        document_text_translation += row[1].strip() + "\n"
                        paragraphs_original.append(row[0].strip())
                        paragraphs_translation.append(row[1].strip())
                    except IndexError:
                        logger.warning('Index out of range in CSV')
                break
            else:
                logger.error('Could not get document: code {0}'.format(response.status_code))
                update.message.reply_text(SHIT_HAPPENS)
                return ConversationHandler.END

    if tries >= 10:
        logger.error('Retry count exceeded')
        update.message.reply_text(SHIT_HAPPENS)
        return ConversationHandler.END

    s3_client = boto3.client('s3',
                             aws_access_key_id=AWS_ACCESS_KEY_ID,
                             aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

    # format

    document_text = "Unknown format"
    if document_format == EXPORT_FORMAT_ORIGINAL_TEXT.lower():
        document_text = process_document_text(document_text_original)
    elif document_format == EXPORT_FORMAT_TRANSLATION_TEXT.lower():
        document_text = process_document_text(document_text_translation)
    elif document_format == EXPORT_FORMAT_PONY_HTML.lower():
        if document['name'] not in LINKS:
            logger.error('Requested chapter is not in links list')
            update.message.reply_text(SHIT_HAPPENS)
            return ConversationHandler.END

        # fetch original if not there yet
        original_filename = slugify(document['name']) + '.html'

        try:
            response = s3_client.get_object(Bucket=AWS_ORIGINALS_BUCKET, Key=original_filename)
            original_html = response['Body'].read().decode('utf-8')
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchKey':
                logger.error('Unexpected exception: {}'.format(e))
                update.message.reply_text(SHIT_HAPPENS)
                return ConversationHandler.END

            original_url = LINKS[document['name']]
            logger.info('Getting the original: {}'.format(original_url))
            response = requests.get(original_url)
            if response.status_code != 200:
                logger.error('Could not get the original')
                update.message.reply_text(SHIT_HAPPENS)
                return ConversationHandler.END

            f = BytesIO(response.content)
            logger.info('Saving {} to S3, bucket {}'.format(original_filename, AWS_ORIGINALS_BUCKET))
            s3_client.upload_fileobj(f, AWS_ORIGINALS_BUCKET, original_filename)

            original_html = response.content.decode('utf-8')

        root = lxml.html.fromstring(original_html)
        elements = root.xpath("//div[@class='entry-content']/p")
        paragraphs = []
        for e in elements:
            p = lxml_stringify_children(e)
            if 'https://pactwebserial.wordpress.com' not in p:  # skip navigation
                paragraphs.append(p)

        logger.info('{} - {}'.format(len(paragraphs_original), len(paragraphs)))
        document_text = ''

    # upload to s3 and get the public link

    content_hash = hashlib.md5(document_text.encode('utf-8')).hexdigest()
    filename = 'pact-' + slugify(document['name']) + '-' + content_hash[:4]
    if document_format == EXPORT_FORMAT_PONY_HTML.lower():
        filename += '.html'
    else:
        filename += '.txt'
    logger.info('Uploading {0} to S3, bucket {1}'.format(filename, AWS_DOCUMENT_BUCKET))
    f = BytesIO(document_text.encode('utf-8'))
    try:
        s3_client.upload_fileobj(f, AWS_DOCUMENT_BUCKET, filename, ExtraArgs={'ACL': 'public-read'})
        file_url = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': AWS_DOCUMENT_BUCKET,
                                                            'Key': filename})
        if '?' in file_url:
            file_url = file_url.split('?')[0]  # query string does not matter in our case
        logger.info('Uploaded, file URL: {0}'.format(file_url))
        update.message.reply_text(DOCUMENT_LINK.format(document['name'], file_url), reply_markup=ReplyKeyboardRemove())
    except ClientError as e:
        logger.error(e)
        update.message.reply_text(SHIT_HAPPENS)

    return ConversationHandler.END


def export_cancel(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text(OK_BYE, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def process_document_text(s):
    """Strip extra spaces, add paragraphs where needed etc"""
    s = s.replace('||', "\n")

    join_paragraphs = re.compile("\\s*<<\\s*", re.MULTILINE)
    s = join_paragraphs.sub(" ", s)

    s = s.replace("\r\n", "\n")
    extra_breaks = re.compile("\n{2,}")
    s = extra_breaks.sub("\n", s)
    s = s.replace("\n", "\r\n")

    extra_spaces = re.compile("[ \t]{2,}")
    s = extra_spaces.sub(" ", s)

    return s.strip()

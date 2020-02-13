# -*- coding: utf-8 -*-
import csv
import hashlib
import json
import logging
import re
import time
from io import StringIO, BytesIO

import boto3
from botocore.exceptions import ClientError
from slugify import slugify
from telegram import ReplyKeyboardRemove
from telegram.ext import ConversationHandler

import constants
from config import *
from smartcat.api import SmartCAT, SmartcatException
from strings import *

logger = logging.getLogger(__name__)


def export_start(update, context):
    update.message.reply_text(ENTER_THE_DOCUMENT_NAME_ID_OR_CANCEL,
                              reply_markup=ReplyKeyboardRemove())
    return constants.STATE_EXPORT


def export_cancel(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text(OK_BYE, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def export(update, context):
    """Export a document on /export command"""
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

    document_text = ''
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
                        document_text += row[1].strip() + "\n"
                    except IndexError:
                        logger.warning('Index out of range in CSV')
                break
            else:
                logger.error('Could not get document: code {0}'.format(response.status_code))
                update.message.reply_text(SHIT_HAPPENS)
                return

    if tries >= 10:
        logger.error('Retry count exceeded')
        update.message.reply_text(SHIT_HAPPENS)
        return ConversationHandler.END

    # upload to s3 and get the public link

    document_text = process_document_text(document_text)
    content_hash = hashlib.md5(document_text.encode('utf-8')).hexdigest()
    filename = 'pact-' + slugify(document['name']) + '-' + content_hash[:4] + '.txt'
    logger.info('Uploading {0} to s3, bucket {1}'.format(filename, AWS_DOCUMENT_BUCKET))
    s3_client = boto3.client('s3',
                             aws_access_key_id=AWS_ACCESS_KEY_ID,
                             aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    f = BytesIO(document_text.encode('utf-8'))
    try:
        s3_client.upload_fileobj(f, AWS_DOCUMENT_BUCKET, filename, ExtraArgs={'ACL': 'public-read'})
        file_url = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': AWS_DOCUMENT_BUCKET,
                                                            'Key': filename})
        if '?' in file_url:
            file_url = file_url.split('?')[0]  # query string does not matter in our case
        logger.info('Uploaded, file URL: {0}'.format(file_url))
        update.message.reply_text(DOCUMENT_LINK.format(document['name'], file_url))
    except ClientError as e:
        logger.error(e)
        update.message.reply_text(SHIT_HAPPENS)

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

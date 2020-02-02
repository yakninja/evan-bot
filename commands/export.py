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

from config import *
from smartcat.api import SmartCAT
from strings import *


def export(update, context):
    """Export a document on /export command"""
    m = re.match("/export\\s+(.+)", update.message.text)
    if not m:
        update.message.reply_text(I_DONT_UNDERSTAND)
        return

    name_or_id = m.groups()[0].lower().strip()
    logging.info('Export request: {0}'.format(name_or_id))

    sc_api = SmartCAT(SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD, SmartCAT.SERVER_EUROPE)
    response = sc_api.project.get(SMARTCAT_PROJECT_ID)
    if response.status_code != 200:
        logging.error('Could get the project info: {0}'.format(SMARTCAT_PROJECT_ID))
        update.message.reply_text(SHIT_HAPPENS)
        return

    project_data = json.loads(response.content.decode('utf-8'))
    if not project_data:
        update.message.reply_text(SHIT_HAPPENS)
        return

    document = None
    for d in project_data['documents']:
        if d['id'] == name_or_id or d['name'].lower() == name_or_id:
            document = d
            break

    if not document:
        logging.info('Document not found')
        update.message.reply_text(NOTHING_FOUND)
        return

    logging.info('Document id: {0}'.format(document['id']))

    response = sc_api.document.request_export(document['id'], target_type='multilangCsv')
    if response.status_code != 200:
        logging.error('Error requesting document export: code {0}'.format(response.status_code))
        update.message.reply_text(SHIT_HAPPENS)
        return

    data = json.loads(response.content.decode('utf-8'))
    if not data or not data['id']:
        logging.error('Error requesting document export: invalid content')
        update.message.reply_text(SHIT_HAPPENS)
        return

    task_id = data['id']
    logging.info('Export task id: {0}'.format(task_id))

    # now wait for the task to complete and get the document text

    document_text = ''
    tries = 1
    while tries < 10:
        time.sleep(tries * tries)
        response = sc_api.document.download_export_result(task_id)
        if response.status_code == 204:
            logging.info('Document not ready yet, retrying...')
            tries += 1
        else:
            if response.status_code == 200:
                f = StringIO(response.content.decode('utf-8'))
                reader = csv.reader(f, delimiter=',')
                next(reader)  # skip header
                for row in reader:
                    try:
                        document_text += row[1].strip() + "\n\n"
                    except IndexError:
                        logging.warning('Index out of range in CSV')
                break
            else:
                logging.error('Could not get document: code {0}'.format(response.status_code))
                update.message.reply_text(SHIT_HAPPENS)
                return

    if tries >= 10:
        logging.error('Retry count exceeded')
        update.message.reply_text(SHIT_HAPPENS)

    # upload to s3 and get the public link

    document_text = process_document_text(document_text)
    content_hash = hashlib.md5(document_text.encode('utf-8')).hexdigest()
    filename = 'pact-' + slugify(document['name']) + '-' + content_hash[:4] + '.txt'
    logging.info('Uploading {0} to s3, bucket {1}'.format(filename, AWS_DOCUMENT_BUCKET))
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
        logging.info('Uploaded, file URL: {0}'.format(file_url))
        update.message.reply_text(DOCUMENT_LINK.format(document['name'], file_url))
    except ClientError as e:
        logging.error(e)
        update.message.reply_text(SHIT_HAPPENS)


def process_document_text(s):
    """Strip extra spaces, add paragraphs where needed etc"""
    s = s.replace('||', "\n")

    join_paragraphs = re.compile("\\s*<<\\s*", re.MULTILINE)
    s = join_paragraphs.sub(" ", s)

    extra_breaks = re.compile("\n{2,}")
    s = extra_breaks.sub("\n", s)

    extra_spaces = re.compile("[ \t]{2,}")
    s = extra_spaces.sub(" ", s)

    return s.strip()

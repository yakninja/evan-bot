# -*- coding: utf-8 -*-
import logging
import re
import time
import csv
from io import StringIO, BytesIO
import hashlib

import boto3
from botocore.exceptions import ClientError
from slugify import slugify

from strings import *
from config import *
import smartcat


def export(update, context):
    """Export a document on /export command"""
    m = re.match("/export\\s+(.+)", update.message.text)
    if not m:
        update.message.reply_text(I_DONT_UNDERSTAND)
        return

    name_or_id = m.groups()[0].lower().strip()
    project_data = smartcat.project_stats()
    if not project_data:
        update.message.reply_text(SHIT_HAPPENS)
        return

    document = None
    for d in project_data['documents']:
        if d['id'] == name_or_id or d['name'].lower() == name_or_id:
            document = d
            break

    if not document:
        update.message.reply_text(NOTHING_FOUND)
        return

    task_id = smartcat.export_request(document['id'])

    # now wait for the task to complete and get the document text

    document_text = ''
    tries = 1
    while tries < 10:
        time.sleep(tries * tries)
        try:
            f = StringIO(smartcat.export(task_id))
            reader = csv.reader(f, delimiter=',')
            next(reader)  # skip header
            for row in reader:
                document_text += row[1].strip() + "\n\n"
            break
        except smartcat.SmartcatException as e:
            if e.code == 204:
                tries += 1  # not yet
            else:
                raise e

    if tries >= 10:
        update.message.reply_text(SHIT_HAPPENS)

    # upload to s3

    document_text = process_document_text(document_text)
    content_hash = hashlib.md5(document_text.encode('utf8')).hexdigest()
    filename = 'pact-' + slugify(document['name']) + '-' + content_hash[:4] + '.txt'
    s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID,
                             aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    f = BytesIO(document_text.encode('utf8'))
    try:
        s3_client.upload_fileobj(f, AWS_DOCUMENT_BUCKET, filename, ExtraArgs={'ACL': 'public-read'})
        file_url = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': AWS_DOCUMENT_BUCKET,
                                                            'Key': filename})
        update.message.reply_text(DOCUMENT_LINK.format(document['name'], file_url))
    except ClientError as e:
        logging.error(e)
        update.message.reply_text(SHIT_HAPPENS)


def process_document_text(s):
    """Strip extra spaces, add paragraphs where needed etc"""
    s = s.replace('||', "\n")

    join_paragraphs = re.compile("\n*<<\n*")
    s = join_paragraphs.sub(" ", s)

    extra_breaks = re.compile("\n{2,}")
    s = extra_breaks.sub("\n", s)

    extra_spaces = re.compile("[ \t]{2,}")
    s = extra_spaces.sub(" ", s)

    return s.strip()

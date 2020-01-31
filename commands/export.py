# -*- coding: utf-8 -*-
import re
import time
import csv
from io import StringIO
import boto3
import boto.s3
import sys
import hashlib
from boto.s3.key import Key
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
    content_hash = ''
    while tries < 10:
        time.sleep(tries * tries)
        try:
            f = StringIO(smartcat.export(task_id))
            reader = csv.reader(f, delimiter=',')
            for row in reader:
                document_text += row[1] + "\n"
            break
        except smartcat.SmartcatException as e:
            if e.code == 204:
                tries += 1  # not yet
            raise e

    if tries >= 10:
        update.message.reply_text(SHIT_HAPPENS)

    # upload to s3

    print('uploading...')
    content_hash = hashlib.md5(document_text.encode('utf8')).hexdigest()
    filename = content_hash + '.txt'
    s3_connection = boto.connect_s3(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    bucket = s3_connection.get_bucket('evan-bot')
    key = boto.s3.key.Key(bucket, filename)
    key.send_file(StringIO(document_text))
    print('uploaded')

    update.message.reply_text(filename)

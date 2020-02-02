# -*- coding: utf-8 -*-
import json
import logging
import re

from config import *
from smartcat import SmartCAT, SmartCATWeb, SmartcatException
from strings import *


def get_document_by_name(update, name_or_id):
    sc_api = SmartCAT(SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    try:
        document = sc_api.project.get_document_by_name(SMARTCAT_PROJECT_ID, name_or_id)
    except SmartcatException as e:
        logging.error('Error getting document: {0} {1}'.format(e.code, e.message))
        update.message.reply_text(SHIT_HAPPENS)
        return None

    if not document:
        logging.warning('Document not found')
        update.message.reply_text(NOTHING_FOUND)
        return None

    return document


def get_document_and_list_id_by_name(update, name_or_id):
    document = get_document_by_name(update, name_or_id)
    if not document:
        return None, None

    logging.info('Document id: {0}'.format(document['id']))

    sc_web = SmartCATWeb(SMARTCAT_SESSION_FILE, SMARTCAT_EMAIL, SMARTCAT_PASSWORD,
                         SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)

    remove_lang = re.compile('_.{2}$')
    response = sc_web.create_document_list_id(remove_lang.sub('', document['id']))
    list_id = json.loads(response.content, encoding='utf-8')
    if not list_id:
        logging.warning('List id not found')
        update.message.reply_text(NOTHING_FOUND)
        return document, None

    return document, list_id

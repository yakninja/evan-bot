# -*- coding: utf-8 -*-
import json
import logging
import re

from config import *
from smartcat import SmartCATWeb, SmartCAT, SmartcatException
from strings import *


def executives(update, context):
    """List executives for the document"""
    m = re.match("/executives\\s+(.+)", update.message.text)
    if not m:
        update.message.reply_text(I_DONT_UNDERSTAND)
        return
    name_or_id = m.groups()[0].lower().strip()
    logging.info('Executives request: {0}'.format(name_or_id))

    sc_api = SmartCAT(SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    try:
        document = sc_api.project.get_document_by_name(SMARTCAT_PROJECT_ID, name_or_id)
    except SmartcatException as e:
        logging.error('Error getting document: {0} {1}'.format(e.code, e.message))
        update.message.reply_text(SHIT_HAPPENS)
        return

    if not document:
        logging.warning('Document not found')
        update.message.reply_text(NOTHING_FOUND)
        return

    logging.info('Document id: {0}'.format(document['id']))

    sc_web = SmartCATWeb(SMARTCAT_EMAIL, SMARTCAT_PASSWORD, SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD,
                         cookie_jar_filename='cookies.txt')

    remove_lang = re.compile('_.{2}$')
    response = sc_web.create_document_list_id(remove_lang.sub('', document['id']))
    list_id = json.loads(response.content, encoding='utf-8')
    if not list_id:
        logging.warning('List id not found')
        update.message.reply_text(NOTHING_FOUND)
        return

    logging.info('List id: {0}'.format(list_id))

    response = sc_web.get_workflow_stages(SMARTCAT_PROJECT_ID, list_id)
    data = json.loads(response.content, encoding='utf-8')
    if not data:
        logging.error('Error getting workflow_stages')
        update.message.reply_text(SHIT_HAPPENS)
        return

    people = {'translation': [], 'editing': []}
    for d in data:
        service = d['name'].lower()
        if d['executives']:
            for e in d['executives']:
                people[service].append(e)

    translators = '(никого)'
    if len(people['translation']):
        translators = "\n".join(e['name'] for e in people['translation'])

    reply = 'Переводчики:\n{0}'.format(translators)

    editors = '(никого)'
    if len(people['editing']):
        editors = "\n".join(e['name'] for e in people['editing'])

    reply += '\n\nРедакторы:\n{0}'.format(editors)

    update.message.reply_text(reply)

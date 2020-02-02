# -*- coding: utf-8 -*-

from helpers import *


def executives(update, context):
    """List executives for the document"""
    m = re.match("/executives\\s+(.+)", update.message.text)
    if not m:
        update.message.reply_text(I_DONT_UNDERSTAND)
        return
    name_or_id = m.groups()[0].lower().strip()
    logging.info('Executives request: {0}'.format(name_or_id))

    document, list_id = get_document_and_list_id_by_name(update, name_or_id)
    if not document or not list_id:
        return

    logging.info('List id: {0}'.format(list_id))

    sc_web = SmartCATWeb(SMARTCAT_SESSION_FILE, SMARTCAT_EMAIL, SMARTCAT_PASSWORD,
                         SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)

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

    translators = NOBODY
    if len(people['translation']):
        translators = "\n".join(e['name'] for e in people['translation'])

    reply = \
        TRANSLATORS + ':\n{0}'.format(translators)

    editors = NOBODY
    if len(people['editing']):
        editors = "\n".join(e['name'] for e in people['editing'])

    reply += '\n\n' + EDITORS + ':\n{0}'.format(editors)

    update.message.reply_text(reply)

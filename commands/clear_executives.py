# -*- coding: utf-8 -*-

from helpers import *


def clear_executives(update, context):
    """List executives for the document"""
    if update.message.from_user.username not in ADMIN_USERS:
        update.message.reply_text(YOU_HAVE_NO_POWER_OVER_ME)
        return

    m = re.match("/clear_executives\\s+(.+?)(\\s+(translation|editing))?$", update.message.text)
    if not m:
        update.message.reply_text(I_DONT_UNDERSTAND)
        return
    name_or_id = m.groups()[0].lower().strip()
    stages = [TRANSLATION_SERVICE_ID, EDITING_SERVICE_ID]
    if m.groups()[1]:
        if m.groups()[1].lower().strip() == 'translation':
            stages = [TRANSLATION_SERVICE_ID]
        else:
            stages = [EDITING_SERVICE_ID]

    logging.info('Clear executives request: {0} {1}'.format(name_or_id, stages))

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

    logging.info(data)
    for stage in stages:
        #  collect ids to remove
        ids_to_remove = []
        for d in data:
            if d['serviceType'] == stage and d['executives']:
                for e in d['executives']:
                    if e['id'] not in ids_to_remove:
                        ids_to_remove.append(e['id'])

        if len(ids_to_remove):
            for eid in ids_to_remove:
                logging.info('Removing id {0} from stage {1}'.format(eid, stage))
                response = sc_web.api.document.unassign(document['id'], stage, eid)
                logging.info('Response status: {0}'.format(response.status_code))

    update.message.reply_text(DONE)

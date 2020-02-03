# -*- coding: utf-8 -*-
from telegram import ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import ConversationHandler

import constants
from helpers import *

logger = logging.getLogger(__name__)


def check_assign_permission(update):
    if update.message.from_user.username not in ADMIN_USERS:
        update.message.reply_text(YOU_HAVE_NO_POWER_OVER_ME)
        return False
    return True


def assign_start(update, context):
    if not check_assign_permission(update):
        return ConversationHandler.END
    logger.info("User %s: /assign", update.message.from_user.username)
    update.message.reply_text("Напиши имена назначаемых через запятую, или /cancel для выхода.",
                              reply_markup=ReplyKeyboardRemove())
    return constants.STATE_CHOOSE_EXECUTIVES


def assign_choose_executives(update, context):
    if not check_assign_permission(update):
        return ConversationHandler.END
    logger.info("User %s: /assign_choose_executives", update.message.from_user.username)
    names = update.message.text.split(',')
    if len(names) == 0:
        update.message.reply_text("Я не могу работать с пустым списком. "
                                  "Напиши имена назначаемых через запятую, или /cancel для выхода",
                                  reply_markup=ReplyKeyboardRemove())
        return constants.STATE_CHOOSE_EXECUTIVES

    sc_web = SmartCATWeb(SMARTCAT_SESSION_FILE, SMARTCAT_EMAIL, SMARTCAT_PASSWORD,
                         SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    reply = ''
    i = 1
    found_count = 0
    context.user_data['executives'] = []
    for name in names:
        name = name.strip()
        logger.info("Getting info on {0}".format(name))
        response = sc_web.api.account.find_executives_by_name(name)
        logger.info("Response code: {0}".format(response.status_code))
        if response.status_code != 200:
            update.message.reply_text(SHIT_HAPPENS)
            return ConversationHandler.END
        data = json.loads(response.content, encoding='utf-8')
        logger.info("Found {0} results".format(len(data)))
        if len(data) == 0:
            reply += "{0}. {1}: не найден\n".format(i, name)
        else:
            found_count += 1
            found_name = data[0]['firstName'] + ' ' + data[0]['lastName']
            context.user_data['executives'].append(data[0])
            if len(data) > 1:
                reply += "{0}. {1}: найдено несколько вариантов, используем первый: {2} ({3})\n".format(
                    i,
                    name,
                    found_name,
                    data[0]['id'],
                )
            else:
                reply += "{0}. {1}: найден ({2})\n".format(
                    i,
                    found_name,
                    data[0]['id'],
                )
        i += 1

    if found_count == 0:
        reply += "\nНикто не найден, попробуй /assign еще раз"
        update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        reply += "\nЕсли все в порядке - введи название или id главы (можно несколько, по одному на строку)\n" \
                 "Чтобы выбрать все главы, введи \"all\"\n" \
                 "Для выхода введи /cancel"
        update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
        return constants.STATE_CHOOSE_DOCUMENT


def assign_choose_document(update, context):
    if not check_assign_permission(update):
        return ConversationHandler.END

    sc_api = SmartCAT(SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    names_or_ids = update.message.text.lower().strip()
    documents = []
    response = sc_api.project.get(SMARTCAT_PROJECT_ID)
    if response.status_code != 200:
        update.message.reply_text(SHIT_HAPPENS + "\nПопробуй еще раз или введи /cancel для выхода")
        return constants.STATE_CHOOSE_DOCUMENT

    project_data = json.loads(response.content.decode('utf-8'))
    if not project_data:
        update.message.reply_text(SHIT_HAPPENS + "\nПопробуй еще раз или введи /cancel для выхода")
        return constants.STATE_CHOOSE_DOCUMENT

    if names_or_ids == 'all':
        documents = project_data['documents']
    else:
        names_or_ids = [s.lower().strip() for s in names_or_ids.split("\n")]
        for d in project_data['documents']:
            if d['id'].lower() in names_or_ids or d['name'].lower().strip() in names_or_ids:
                logger.info("Document added: {0} {1}".format(d['id'], d['name']))
                documents.append(d)

    if len(documents) == 0:
        update.message.reply_text(NOTHING_FOUND + "\nПопробуй еще раз или введи /cancel для выхода")
        return constants.STATE_CHOOSE_DOCUMENT

    context.user_data['documents'] = documents

    if len(documents) == 1:
        reply = "Ок, я нашел одну главу: {0} ({1})".format(documents[0]['name'], documents[0]['id'])
    else:
        reply = "Ок, я нашел {0} глав.\n".format(len(documents))
        for d in documents:
            reply += "- {0} {1}\n".format(d['name'], d['id'])

    reply += "\nТеперь выбери куда назначаем этих людей (или /cancel для выхода)"
    reply_keyboard = [['Переводчики', 'Редакторы']]
    update.message.reply_text(reply, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return constants.STATE_CHOOSE_STAGE


def assign_choose_stage(update, context):
    if not check_assign_permission(update):
        return ConversationHandler.END

    stage = constants.TRANSLATION_SERVICE_ID if update.message.text.lower().strip() == 'переводчики' \
        else constants.EDITING_SERVICE_ID
    stage_name = 'переводчиков' if stage == constants.TRANSLATION_SERVICE_ID else 'редакторов'
    documents = context.user_data['documents']

    reply = "Хорошо, назначаю " + stage_name;

    if len(documents) == 1:
        reply += " в главу " + documents[0]['name'] + "\n"
    else:
        reply += " в {0} вышеупомянутых глав\n".format(len(documents))

    sc_web = SmartCATWeb(SMARTCAT_SESSION_FILE, SMARTCAT_EMAIL, SMARTCAT_PASSWORD,
                         SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    reply_count = 0
    for d in documents:
        ids = []
        for e in context.user_data['executives']:
            if reply_count < 10:
                reply += e['firstName'] + ' ' + e['lastName'] + ': '
            response = sc_web.api.document.assign(d['id'], stage, e['id'])
            ids.append(e['id'])
            if reply_count < 10:
                reply += ('OK' if response.status_code == 204 else '?') + "\n"
            reply_count += 1

        remove_lang = re.compile('_.{2}$')
        response = sc_web.create_document_list_id(remove_lang.sub('', d['id']))
        list_id = json.loads(response.content, encoding='utf-8')

        data = {
            'targetLanguageId': 25,
            'addedAssignedUserIds': ids,
            'removedAssignedUserIds': [],
            'removedInvitedUserIds': [],
            'saveDeadline': False,
            'deadline': None,
        }
        response = sc_web.confirm_assignments(SMARTCAT_PROJECT_ID, list_id, stage, data)
        logger.info('confirm_assignments: {0}'.format(response.status_code))
    if reply_count >= 10:
        reply += "...\n"
    update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def assign_cancel(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text(OK_BYE, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

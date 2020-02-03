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
        reply += "\nЕсли все в порядке - введи название или id главы. Если нет - введи /cancel и попытайся снова."
        update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
        return constants.STATE_CHOOSE_DOCUMENT


def assign_choose_document(update, context):
    if not check_assign_permission(update):
        return ConversationHandler.END

    name_or_id = update.message.text.strip()

    sc_api = SmartCAT(SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    try:
        document = sc_api.project.get_document_by_name(SMARTCAT_PROJECT_ID, name_or_id)
    except SmartcatException as e:
        logger.error('Error getting document: {0} {1}'.format(e.code, e.message))
        update.message.reply_text(SHIT_HAPPENS + "\nПопробуй еще раз или введи /cancel для выхода")
        return constants.STATE_CHOOSE_DOCUMENT

    if not document:
        logger.warning('Document not found')
        update.message.reply_text(NOTHING_FOUND + "\nПопробуй еще раз или введи /cancel для выхода")
        return constants.STATE_CHOOSE_DOCUMENT

    logger.info('Document id: {0}'.format(document['id']))
    context.user_data['document'] = document

    reply = "Ок, я нашел эту главу: {0} ({1})".format(document['name'], document['id'])
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

    reply = "Хорошо, назначаю " + stage_name + \
            " в главу " + context.user_data['document']['name'] + "\n"

    sc_web = SmartCATWeb(SMARTCAT_SESSION_FILE, SMARTCAT_EMAIL, SMARTCAT_PASSWORD,
                         SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    ids = []
    for e in context.user_data['executives']:
        reply += e['firstName'] + ' ' + e['lastName'] + ': '
        response = sc_web.api.document.assign(context.user_data['document']['id'], stage, e['id'])
        ids.append(e['id'])
        reply += ('OK' if response.status_code == 204 else '?') + "\n"

    remove_lang = re.compile('_.{2}$')
    response = sc_web.create_document_list_id(remove_lang.sub('', context.user_data['document']['id']))
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
    logger.info(response.content)
    update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def assign_cancel(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text(OK_BYE, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def assign(update, context):
    """Assign translator/editor to a document"""
    if not check_assign_permission(update):
        return ConversationHandler.END

    m = re.match("/assign\\s+(translation|editing)\\s+(\\S+)(\\s+.+)?", update.message.text)
    if not m:
        update.message.reply_text(I_DONT_UNDERSTAND)
        return

    stage = m.groups()[0]
    username = m.groups()[1]
    name_or_id = m.groups()[2].strip()
    logging.info('Assign: stage {0}, username {1}, document {2}'.format(stage, username, name_or_id))

    document = get_document_by_name(update, name_or_id)
    if not document:
        return

    update.message.reply_text(DONE)

# -*- coding: utf-8 -*-
from telegram import ReplyKeyboardMarkup

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

    reply = choose_executives(update, context)

    if len(context.user_data['executives']) == 0:
        reply += "\nНикто не найден, попробуй /assign еще раз"
        update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        reply += "\nКакие главы?"
        reply_keyboard = [[
            ALL_CHAPTERS,
            ACTIVE_CHAPTERS,
            CHAPTERS_BEING_TRANSLATED,
            CHAPTERS_BEING_EDITED,
            '/cancel',
        ]]
        update.message.reply_text(reply, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
        return constants.STATE_CHOOSE_DOCUMENT


def assign_choose_document(update, context):
    if not check_assign_permission(update):
        return ConversationHandler.END

    reply = choose_documents(update, context)

    reply += "\nТеперь выбери на какую роль назначаем этих людей в эти главы (или /cancel для выхода)"
    reply_keyboard = [[
        'Переводчики',
        'Редакторы',
        '/cancel',
    ]]
    update.message.reply_text(reply, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return constants.STATE_CHOOSE_STAGE


def assign_choose_stage(update, context):
    if not check_assign_permission(update):
        return ConversationHandler.END

    stage = constants.TRANSLATION_SERVICE_ID if update.message.text.lower().strip() == 'переводчики' \
        else constants.EDITING_SERVICE_ID
    stage_name = 'переводчиков' if stage == constants.TRANSLATION_SERVICE_ID else 'редакторов'
    documents = context.user_data['documents']

    reply = "Хорошо, назначаю " + stage_name

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

        # for all these users we need to check "Do not calculate the cost of work"
        if len(ids):
            logger.info('Checking "Do not calculate the cost of work"...')
            for user_id in ids:
                response = sc_web.reset_services(user_id)
                logger.info('Status: %s' % response.status_code)

    if reply_count >= 10:
        reply += "...\n"
    update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def assign_cancel(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text(OK_BYE, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

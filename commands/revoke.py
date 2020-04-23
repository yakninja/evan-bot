# -*- coding: utf-8 -*-
from telegram import ReplyKeyboardMarkup

from helpers import *

logger = logging.getLogger(__name__)


def check_revoke_permission(update):
    if update.message.from_user.username not in ADMIN_USERS:
        update.message.reply_text(YOU_HAVE_NO_POWER_OVER_ME)
        return False
    return True


def revoke_start(update, context):
    if not check_revoke_permission(update):
        return ConversationHandler.END
    logger.info("User %s: /revoke", update.message.from_user.username)
    update.message.reply_text("Напиши имена удаляемых через запятую, или /cancel для выхода.",
                              reply_markup=ReplyKeyboardRemove())
    return constants.STATE_CHOOSE_EXECUTIVES


def revoke_choose_executives(update, context):
    if not check_revoke_permission(update):
        return ConversationHandler.END

    reply = choose_executives(update, context)

    if len(context.user_data['executives']) == 0:
        reply += "\nНикто не найден, попробуй /revoke еще раз"
        update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        reply += "\nЕсли все в порядке - введи название или id главы (можно несколько, по одному на строку)\n" \
                 "Чтобы выбрать все главы, введи \"all\"\n" \
                 "Для выхода введи /cancel"
        update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
        return constants.STATE_CHOOSE_DOCUMENT


def revoke_choose_document(update, context):
    if not check_revoke_permission(update):
        return ConversationHandler.END

    reply = choose_documents(update, context)

    reply += "\nТеперь выбери с какой роли убираем этих людей из этих глав (или /cancel для выхода)"
    reply_keyboard = [['Переводчики', 'Редакторы']]
    update.message.reply_text(reply, reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return constants.STATE_CHOOSE_STAGE


def revoke_choose_stage(update, context):
    if not check_revoke_permission(update):
        return ConversationHandler.END

    stage = constants.TRANSLATION_SERVICE_ID if update.message.text.lower().strip() == 'переводчики' \
        else constants.EDITING_SERVICE_ID
    stage_name = 'переводчиков' if stage == constants.TRANSLATION_SERVICE_ID else 'редакторов'

    documents = context.user_data['documents']

    reply = "Хорошо, убираю " + stage_name

    if len(documents) == 1:
        reply += " из главы " + documents[0]['name'] + "\n"
    else:
        reply += " из {0} вышеупомянутых глав\n".format(len(documents))

    sc_web = SmartCATWeb(SMARTCAT_SESSION_FILE, SMARTCAT_EMAIL, SMARTCAT_PASSWORD,
                         SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)

    reply_count = 0
    for d in documents:
        for e in context.user_data['executives']:
            if reply_count < 10:
                reply += e['firstName'] + ' ' + e['lastName'] + ': '
            response = sc_web.api.document.unassign(d['id'], stage, e['id'])
            if reply_count < 10:
                reply += ('OK' if response.status_code == 204 else '?') + "\n"
            reply_count += 1

    if reply_count >= 10:
        reply += "...\n"

    update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def revoke_cancel(update, context):
    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    update.message.reply_text(OK_BYE, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

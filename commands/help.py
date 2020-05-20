# -*- coding: utf-8 -*-
from telegram import ReplyKeyboardRemove
from telegram.ext import ConversationHandler


def help(update, context):
    """Send a message when the command /help is issued."""
    reply = """Список моих команд:
/stats — статистика перевода
/export — экспорт оригинала или перевода

/executives [документ] — список пользователей, работающих над главой
/clear_executives [документ] — очистить список работающих над главой
/assign назначить участников на перевод или редактирование
/revoke удалить пользователя из переводчиков или редакторов

Подробнее о моей работе можно почитать здесь:
https://github.com/yakninja/evan-bot
    """
    update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# -*- coding: utf-8 -*-


def help(update, context):
    """Send a message when the command /help is issued."""
    reply = """/export [название или id документа] - экспорт в текст
    """
    update.message.reply_text(reply)

# -*- coding: utf-8 -*-


def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Привет! :)')

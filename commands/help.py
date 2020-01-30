# -*- coding: utf-8 -*-


def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')

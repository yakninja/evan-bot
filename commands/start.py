# -*- coding: utf-8 -*-
from strings import *


def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text(START_HELLO)

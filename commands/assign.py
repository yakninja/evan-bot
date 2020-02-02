# -*- coding: utf-8 -*-
import logging
import re

from config import *
from strings import *


def assign(update, context):
    """Assign editor"""
    if update.message.from_user.username not in ADMIN_USERS:
        update.message.reply_text(YOU_HAVE_NO_POWER_OVER_ME)
        return

    m = re.match("/assign\\s+(translate|edit)\\s+(\\S+)(\\s+.+)?", update.message.text)
    if not m:
        update.message.reply_text(I_DONT_UNDERSTAND)
        return

    stage = m.groups()[0]
    username = m.groups()[1]
    document_id_or_name = m.groups()[2].strip()
    logging.info('Assign: stage {0}, username {1}, document {2}'.format(stage, username, document_id_or_name))
    update.message.reply_text('ok')

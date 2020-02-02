# -*- coding: utf-8 -*-

from helpers import *


def assign(update, context):
    """Assign editor"""
    if update.message.from_user.username not in ADMIN_USERS:
        update.message.reply_text(YOU_HAVE_NO_POWER_OVER_ME)
        return

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

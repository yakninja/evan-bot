# -*- coding: utf-8 -*-
from strings import *
from config import *
from smartcat import *
import re


def export(update, context):
    """Export a document on /export command"""
    m = re.match("/export\\s+(.+)", update.message.text)
    if not m:
        update.message.reply_text(I_DONT_UNDERSTAND)
        return

    name_or_id = m.groups()[0].lower().strip()

    update.message.reply_text(name_or_id)

# -*- coding: utf-8 -*-
from strings import *
from config import *
import smartcat
import re


def export(update, context):
    """Export a document on /export command"""
    m = re.match("/export\\s+(.+)", update.message.text)
    if not m:
        update.message.reply_text(I_DONT_UNDERSTAND)
        return

    name_or_id = m.groups()[0].lower().strip()
    project_data = smartcat.project_stats()
    if not project_data:
        update.message.reply_text(SHIT_HAPPENS)
        return

    document = None
    for d in project_data['documents']:
        if d['id'] == name_or_id or d['name'].lower() == name_or_id:
            document = d
            break

    if not document:
        update.message.reply_text(NOTHING_FOUND)
        return

    update.message.reply_text(document['id'])

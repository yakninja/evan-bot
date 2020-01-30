# -*- coding: utf-8 -*-
from strings import *
from config import *
import smartcat
import re


def stats(update, context):
    """Get some stats from Smartcat"""
    data = smartcat.project_stats()
    if not data:
        update.message.reply_text(SHIT_HAPPENS)
        return

    translation_stage = {}
    editing_stage = {}
    for stage in data['workflowStages']:
        if stage['stageType'] == 'translation':
            translation_stage = stage
        if stage['stageType'] == 'editing':
            editing_stage = stage
    s = [
        "Глав в работе: {0}".format(len(data['documents'])),
    ]

    if len(translation_stage):
        s.append("Переведено: {:.0f}%".format(translation_stage['progress']))
    if len(editing_stage):
        s.append("Отредактировано: {:.0f}%".format(editing_stage['progress']))

    update.message.reply_text("Немного статистики!\n" + "\n".join(s))

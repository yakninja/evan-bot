# -*- coding: utf-8 -*-
import json
import logging

from config import *
from smartcat.api import SmartCAT
from strings import *


def stats(update, context):
    """Get some stats from Smartcat"""

    sc_api = SmartCAT(SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD, SmartCAT.SERVER_EUROPE)
    response = sc_api.project.get(SMARTCAT_PROJECT_ID)
    if response.status_code != 200:
        logging.error('Could get the project info: {0}'.format(SMARTCAT_PROJECT_ID))
        update.message.reply_text(SHIT_HAPPENS)
        return

    data = json.loads(response.content.decode('utf-8'))
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

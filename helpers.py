# -*- coding: utf-8 -*-
import json
import logging
import re

from telegram import ReplyKeyboardRemove
from telegram.ext import ConversationHandler

import constants
from config import *
from smartcat import SmartCAT, SmartCATWeb, SmartcatException
from strings import *

logger = logging.getLogger(__name__)


def get_document_by_name(update, name_or_id):
    """Get document list from API and look there for a document with a name (or id).
    Will make a reply from the bot if something goes wrong or the document was not found

    :param update: Update object of the bot.
    :param name_or_id: Document id or name, case insensitive.
    :return str
    """
    sc_api = SmartCAT(SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    try:
        document = sc_api.project.get_document_by_name(SMARTCAT_PROJECT_ID, name_or_id)
    except SmartcatException as e:
        logging.error('Error getting document: {0} {1}'.format(e.code, e.message))
        update.message.reply_text(SHIT_HAPPENS)
        return None

    if not document:
        logging.warning('Document not found')
        update.message.reply_text(NOTHING_FOUND)
        return None

    return document


def get_document_and_list_id_by_name(update, name_or_id):
    """Get document list from API and look there for a document with a name (or id).
    Will also create a document list id (a thing in smartcat which is used to assign/unassign executives)
    Will make a reply from the bot if something goes wrong or the document was not found

    :param update: Update object of the bot.
    :param name_or_id: Document id or name, case insensitive.
    :return (dict, str): document, list_id
    """
    document = get_document_by_name(update, name_or_id)
    if not document:
        return None, None

    logging.info('Document id: {0}'.format(document['id']))

    sc_web = SmartCATWeb(SMARTCAT_SESSION_FILE, SMARTCAT_EMAIL, SMARTCAT_PASSWORD,
                         SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)

    remove_lang = re.compile('_.{2}$')
    response = sc_web.create_document_list_id(remove_lang.sub('', document['id']))
    list_id = json.loads(response.content, encoding='utf-8')
    if not list_id:
        logging.warning('List id not found')
        update.message.reply_text(NOTHING_FOUND)
        return document, None

    return document, list_id


def choose_executives(update, context):
    """Get a list of executives by names and put them into context
    If something goes wrong, replies with a warning message and redirects user to the same stage

    :param update: Update object of the bot.
    :param context:
    :return str: reply from bot
    """
    logger.info("User %s: choose_executives", update.message.from_user.username)
    names = update.message.text.split(',')
    if len(names) == 0:
        update.message.reply_text("Я не могу работать с пустым списком. "
                                  "Напиши имена через запятую, или /cancel для выхода",
                                  reply_markup=ReplyKeyboardRemove())
        return constants.STATE_CHOOSE_EXECUTIVES

    sc_web = SmartCATWeb(SMARTCAT_SESSION_FILE, SMARTCAT_EMAIL, SMARTCAT_PASSWORD,
                         SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    reply = ''
    i = 1
    found_count = 0
    context.user_data['executives'] = []
    for name in names:
        name = name.strip()
        logger.info("Getting info on {0}".format(name))
        response = sc_web.api.account.search_my_team({
            "skip": 0,
            "limit": 10,
            "searchString": name
        })
        logger.info("Response code: {0}".format(response.status_code))
        if response.status_code != 200:
            update.message.reply_text(SHIT_HAPPENS)
            return ConversationHandler.END
        data = json.loads(response.content, encoding='utf-8')
        logger.info("Found {0} results".format(len(data)))
        if len(data) == 0:
            reply += "{0}. {1}: не найден\n".format(i, name)
        else:
            found_count += 1
            found_name = data[0]['firstName'] + ' ' + data[0]['lastName']
            context.user_data['executives'].append(data[0])
            if len(data) > 1:
                reply += "{0}. {1}: найдено несколько вариантов, используем первый: {2} ({3})\n".format(
                    i,
                    name,
                    found_name,
                    data[0]['id'],
                )
            else:
                reply += "{0}. {1}: найден ({2})\n".format(
                    i,
                    found_name,
                    data[0]['id'],
                )
        i += 1
        return reply


def choose_documents(update, context):
    """Get a list of documents by names/ids and put them into context
    If something goes wrong, replies with a warning message and redirects user to the same stage

    :param update: Update object of the bot.
    :param context:
    :return str: reply from bot
    """
    sc_api = SmartCAT(SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
    names_or_ids = update.message.text.lower().strip()
    documents = []
    response = sc_api.project.get(SMARTCAT_PROJECT_ID)
    if response.status_code != 200:
        update.message.reply_text(SHIT_HAPPENS + "\nПопробуй еще раз или введи /cancel для выхода")
        return constants.STATE_CHOOSE_DOCUMENT

    project_data = json.loads(response.content.decode('utf-8'))
    if not project_data:
        update.message.reply_text(SHIT_HAPPENS + "\nПопробуй еще раз или введи /cancel для выхода")
        return constants.STATE_CHOOSE_DOCUMENT

    logger.info('names_or_ids = {}'.format(names_or_ids))
    if names_or_ids == ALL_CHAPTERS.lower():
        documents = project_data['documents']
    elif names_or_ids == ACTIVE_CHAPTERS.lower():
        for d in project_data['documents']:
            logger.info("{} - {}".format(d['name'], get_document_stage(d)))
            if get_document_stage(d) < constants.CHAPTER_STATE_FINAL_EDITING:
                logger.info("Document added: {0} {1}".format(d['id'], d['name']))
                documents.append(d)
    elif names_or_ids == CHAPTERS_BEING_TRANSLATED.lower():
        for d in project_data['documents']:
            if get_document_stage(d) == constants.CHAPTER_STATE_TRANSLATION:
                logger.info("Document added: {0} {1}".format(d['id'], d['name']))
                documents.append(d)
    elif names_or_ids == CHAPTERS_BEING_EDITED.lower():
        for d in project_data['documents']:
            if get_document_stage(d) == constants.CHAPTER_STATE_EDITING:
                logger.info("Document added: {0} {1}".format(d['id'], d['name']))
                documents.append(d)
    else:
        names_or_ids = [s.lower().strip() for s in names_or_ids.split("\n")]
        for d in project_data['documents']:
            if d['id'].lower() in names_or_ids or d['name'].lower().strip() in names_or_ids:
                logger.info("Document added: {0} {1}".format(d['id'], d['name']))
                documents.append(d)

    if len(documents) == 0:
        update.message.reply_text(NOTHING_FOUND + "\nПопробуй еще раз или введи /cancel для выхода")
        return constants.STATE_CHOOSE_DOCUMENT

    context.user_data['documents'] = documents

    if len(documents) == 1:
        reply = "Ок, я нашел одну главу: {0} ({1})".format(documents[0]['name'], documents[0]['id'])
    else:
        reply = "Ок, я нашел {0} глав.\n".format(len(documents))
        for d in documents:
            stage_name = constants.CHAPTER_STAGE_NAMES[get_document_stage(d)]
            reply += "- {0}: {1}\n".format(stage_name, d['name'])

    return reply


def get_document_stage(document):
    """
    Get document workflow stage. We can't really get it from API so we're making some guesses
    :param document:
    :return:
    """
    if document['status'] == constants.CHAPTER_STATUS_COMPLETED:
        return constants.CHAPTER_STATE_FINAL_EDITING
    translation_stage = document['workflowStages'][0]
    if translation_stage['progress'] > 99:
        return constants.CHAPTER_STATE_EDITING
    return constants.CHAPTER_STATE_TRANSLATION


def find_chapter_starting_as(name, project_data=None):
    """Find first chapter with name starting with :name
    :param name:
    :param project_data:
    :return dict
    """
    if project_data is None:
        sc_api = SmartCAT(SMARTCAT_API_USERNAME, SMARTCAT_API_PASSWORD)
        response = sc_api.project.get(SMARTCAT_PROJECT_ID)
        if response.status_code != 200:
            return None

        project_data = json.loads(response.content.decode('utf-8'))
        if not project_data:
            return None

    name = name.strip().lower()
    for d in project_data['documents']:
        document_name = d['name'].lower()
        if document_name[:len(name)] == name:
            return d

    return None

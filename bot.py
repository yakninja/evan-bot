import random
import requests
import re
import time

from telegram import Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters

import commands
from helpers import *
from links import *
from strings import *
from chatgpt import call_chatgpt

CHAT_TYPE_PRIVATE = 'private'
ENTITY_TYPE_MENTION = 'mention'

logger = logging.getLogger(__name__)


def bot_name_pattern():
    """Used to determine bot name mention in is_spoken_to()"""
    return "\\b(" + \
           "|".join(NAMES) + \
           "|" + bot.first_name.lower() + \
           "|" + bot.username.lower() + \
           ")[ ,.!?]"


def normalize_message(message_text):
    """Remove bot name, extra spaces etc"""
    message_text = message_text.lower()
    message_text = message_text.replace(
        '@' + bot.username.lower(), ' ').strip()
    p = re.compile(bot_name_pattern())
    message_text = p.sub(' ', message_text).strip()
    p = re.compile('\\s+')
    message_text = p.sub(' ', message_text).strip()
    return message_text


def is_spoken_to(update, context):
    """Returns true if bot is spoken to (private chat, direct mention or message starts with the bot's name)"""
    if update.message.chat['type'] == CHAT_TYPE_PRIVATE:
        return True

    mentions = []
    for entity in update.message.entities:
        if entity['type'] == ENTITY_TYPE_MENTION:
            mentions.append(entity)

    if len(mentions) == 0:
        # no direct mentions, look for names in text
        if re.search(bot_name_pattern(), update.message.text.lower()):
            return True
    else:
        for mention in mentions:
            m = update.message.text[mention.offset +
                                    1:mention.offset + mention.length]
            logger.info('mention: "%s"', m)
            if m == bot.username:
                return True

    return False


def greeting(update, context):
    """Greeting new chat members"""
    logger.info(update.message)
    reply_text = random.choice(NEW_CHAT_MEMBER_GREETINGS).format(
        update.message.new_chat_members[0]['first_name'])
    if reply_text:
        update.message.reply_text(reply_text)


def message(update, context):
    """Reply only if spoken to"""
    from_user = update.message.from_user.first_name
    if update.message.from_user.last_name:
        from_user += ' ' + update.message.from_user.last_name
    if update.message.from_user.username:
        from_user += ' @' + update.message.from_user.username
    logger.info('%s: "%s"', from_user, update.message.text)

    logger.info(update.message)
    reply_text = None
    reply_to_message_id = update.message.message_id

    random.seed()
    if is_spoken_to(update, context):
        message_text = normalize_message(update.message.text)
        if re.search(HELLO_REGEX, message_text):
            reply_text = HELLO_THERE
        else:
            choices = re.match(OR_REGEX, message_text)
            if choices:
                if choices.groups()[0] == choices.groups()[1]:
                    reply_text = YOURE_MAKING_FUN_OF_ME
                else:
                    reply_text = random.choice(choices.groups())
            else:
                # todo: move this to module
                chapter = re.match(CHAPTER_REGEX, message_text)
                if chapter:
                    document = find_chapter_starting_as(
                        chapter.groups()[0].strip())
                    if document is None:
                        reply_text = NOTHING_FOUND
                    else:
                        stage = constants.CHAPTER_STAGE_NAMES[get_document_stage(
                            document)]
                        reply_text = "{0}, статус: {1}".format(
                            document['name'], stage)
                        if document['name'] in LINKS:
                            reply_text += "\nОригинал: {}".format(
                                LINKS[document['name']])
                        if document['name'] in CHAPTER_DOCS:
                            reply_text += "\nСсылка на редактирование: {}".format(
                                CHAPTER_DOCS[document['name']])
                        if document['name'] in PUBLISHED_DOCS:
                            for url in PUBLISHED_DOCS[document['name']]:
                                reply_text += "\nОпубликовано: {}".format(url)
                else:
                    history = []
                    reply_to_message = update.message.reply_to_message
                    if reply_to_message and reply_to_message.from_user.is_bot:
                        logger.info('This is a reply to message:')
                        logger.info(reply_to_message)
                        history.append(
                            {"role": "system", "content": reply_to_message.text})
                    reply_text = call_chatgpt(
                        update.message.from_user,
                        message_text,
                        history=history)
                    logger.info(reply_text)

    if reply_text:
        update.message.reply_text(reply_text,
                                  disable_web_page_preview=True,
                                  reply_to_message_id=reply_to_message_id)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


bot = Bot(os.environ['TELEGRAM_TOKEN'])
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

# on different commands - answer in Telegram
dispatcher.add_handler(CommandHandler("start", commands.start))
dispatcher.add_handler(CommandHandler("help", commands.help))
dispatcher.add_handler(CommandHandler("executives", commands.executives))
dispatcher.add_handler(CommandHandler(
    "clear_executives", commands.clear_executives))
dispatcher.add_handler(CommandHandler("stats", commands.stats))

# Add conversation handlers
dispatcher.add_handler(ConversationHandler(
    entry_points=[CommandHandler('export', commands.export_start)],
    states={
        constants.STATE_EXPORT_CHOOSE_FORMAT: [MessageHandler(Filters.text, commands.export_choose_format)],
        constants.STATE_EXPORT: [MessageHandler(Filters.text, commands.export)],
    },
    fallbacks=[CommandHandler('cancel', commands.export_cancel)]
))
dispatcher.add_handler(ConversationHandler(
    entry_points=[CommandHandler('assign', commands.assign_start)],
    states={
        constants.STATE_START: [MessageHandler(Filters.text, commands.assign_start)],
        constants.STATE_CHOOSE_EXECUTIVES: [MessageHandler(Filters.text, commands.assign_choose_executives)],
        constants.STATE_CHOOSE_DOCUMENT: [MessageHandler(Filters.text, commands.assign_choose_document)],
        constants.STATE_CHOOSE_STAGE: [MessageHandler(Filters.text, commands.assign_choose_stage)],
    },
    fallbacks=[CommandHandler('cancel', commands.assign_cancel)]
))
dispatcher.add_handler(ConversationHandler(
    entry_points=[CommandHandler('revoke', commands.revoke_start)],
    states={
        constants.STATE_START: [MessageHandler(Filters.text, commands.revoke_start)],
        constants.STATE_CHOOSE_EXECUTIVES: [MessageHandler(Filters.text, commands.revoke_choose_executives)],
        constants.STATE_CHOOSE_DOCUMENT: [MessageHandler(Filters.text, commands.revoke_choose_document)],
        constants.STATE_CHOOSE_STAGE: [MessageHandler(Filters.text, commands.revoke_choose_stage)],
    },
    fallbacks=[CommandHandler('cancel', commands.revoke_cancel)]
))

# greeting new members
dispatcher.add_handler(MessageHandler(
    Filters.status_update.new_chat_members, greeting))

# default message handler
dispatcher.add_handler(MessageHandler(Filters.text, message))

# error handler
dispatcher.add_error_handler(error)

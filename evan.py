#!/usr/bin/env python
# -*- coding: utf-8 -*-
import random

import markovify
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters)

import commands
from helpers import *

updater = None

ENTITY_TYPE_MENTION = 'mention'

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)


def is_spoken_to(update, context):
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
            m = update.message.text[mention.offset + 1:mention.offset + mention.length]
            logger.info('mention: "%s"', m)
            if m == updater.bot.username:
                return True

    return False


def bot_name_pattern():
    return "\\b(" + \
           "|".join(NAMES) + \
           "|" + updater.bot.first_name.lower() + \
           "|" + updater.bot.username.lower() + \
           ")[ ,.!?]"


def normalize_message(message_text):
    """Remove bot name, extra spaces etc"""
    message_text = message_text.lower()
    message_text = message_text.replace('@' + updater.bot.username.lower(), ' ').strip()
    p = re.compile(bot_name_pattern())
    message_text = p.sub(' ', message_text).strip()
    p = re.compile('\\s+')
    message_text = p.sub(' ', message_text).strip()
    return message_text


def message(update, context):
    """Reply only if spoken to"""
    from_user = update.message.from_user.first_name
    if update.message.from_user.last_name:
        from_user += ' ' + update.message.from_user.last_name
    if update.message.from_user.username:
        from_user += ' @' + update.message.from_user.username
    logger.info('%s: "%s"', from_user, update.message.text)

    if not is_spoken_to(update, context):
        logger.info(update.message)
        return

    random.seed()
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
                document = find_chapter_starting_as(chapter.groups()[0].strip())
                if document is None:
                    reply_text = NOTHING_FOUND
                else:
                    reply_text = document['name']
                    if document['name'] in CHAPTER_DOCS:
                        reply_text += "\nСсылка на редактирование: {0}".format(CHAPTER_DOCS[document['name']])
            else:
                reply_text = text_model.make_short_sentence(200)

    if reply_text:
        update.message.reply_text(reply_text)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


text_model = None


def main():
    """Start the bot."""
    global updater
    global text_model
    logger.info("Building text model...")

    # Get raw text as string.
    with open("corpus.txt", encoding="utf-8") as f:
        text = f.read()

    # Build the model.
    text_model = markovify.Text(text, 2)

    logger.info("Starting...")
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(TOKEN, use_context=True)
    logger.info("Started! Bot name: %s, username: %s", updater.bot.first_name, updater.bot.username)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", commands.start))
    dp.add_handler(CommandHandler("help", commands.help))
    dp.add_handler(CommandHandler("executives", commands.executives))
    dp.add_handler(CommandHandler("clear_executives", commands.clear_executives))
    dp.add_handler(CommandHandler("stats", commands.stats))

    # Add conversation handlers
    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('export', commands.export_start)],
        states={
            constants.STATE_EXPORT: [MessageHandler(Filters.text, commands.export)]
        },
        fallbacks=[CommandHandler('cancel', commands.export_cancel)]
    ))
    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('assign', commands.assign_start)],
        states={
            constants.STATE_START: [MessageHandler(Filters.text, commands.assign_start)],
            constants.STATE_CHOOSE_EXECUTIVES: [MessageHandler(Filters.text, commands.assign_choose_executives)],
            constants.STATE_CHOOSE_DOCUMENT: [MessageHandler(Filters.text, commands.assign_choose_document)],
            constants.STATE_CHOOSE_STAGE: [MessageHandler(Filters.text, commands.assign_choose_stage)],
        },
        fallbacks=[CommandHandler('cancel', commands.assign_cancel)]
    ))
    dp.add_handler(ConversationHandler(
        entry_points=[CommandHandler('revoke', commands.revoke_start)],
        states={
            constants.STATE_START: [MessageHandler(Filters.text, commands.revoke_start)],
            constants.STATE_CHOOSE_EXECUTIVES: [MessageHandler(Filters.text, commands.revoke_choose_executives)],
            constants.STATE_CHOOSE_DOCUMENT: [MessageHandler(Filters.text, commands.revoke_choose_document)],
            constants.STATE_CHOOSE_STAGE: [MessageHandler(Filters.text, commands.revoke_choose_stage)],
        },
        fallbacks=[CommandHandler('cancel', commands.revoke_cancel)]
    ))

    # on non-command i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, message))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()

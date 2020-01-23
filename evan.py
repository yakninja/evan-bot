#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import logging

from telegram import ReplyKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler)
from config import TOKEN, NAMES
updater = None

ENTITY_TYPE_MENTION = 'mention'

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    update.message.reply_text('Привет! :)')


def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')


def is_spoken_to(update, context):
    mentions = []
    for entity in update.message.entities:
        if entity['type'] == ENTITY_TYPE_MENTION:
            mentions.append(entity)

    if len(mentions) == 0:
        # no direct mentions, look for names in text
        pattern = "\\b(" + \
                  "|".join(NAMES) + \
                  "|" + updater.bot.first_name.lower() + \
                  "|" + updater.bot.username.lower() + \
                  ")[,.!]"
        logger.info('pattern: %s', pattern)
        if re.search(pattern, update.message.text.lower()):
            return True
    else:
        for mention in mentions:
            m = update.message.text[mention.offset + 1:mention.offset + mention.length]
            logger.info('mention: "%s"', m)
            if m == updater.bot.username:
                return True

    return False


def reply(update, context):
    """Reply only if spoken to"""
    if not is_spoken_to(update, context):
        return

    message_text = update.message.text.lower()
    if re.search('(привет|здравст|здраст)', message_text):
        reply_text = 'привет :)'
    else:
        reply_text = 'я не понимаю :('

    update.message.reply_text(reply_text)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    """Start the bot."""
    global updater
    logger.info("Starting...")
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(TOKEN, use_context=True)
    logger.info("Started. Bot name: %s, username: %s", updater.bot.first_name, updater.bot.username)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, reply))

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

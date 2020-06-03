import logging
import os

from telegram import Bot
from telegram.ext import Dispatcher, MessageHandler, Filters

from handlers.message import message

logger = logging.getLogger(__name__)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


bot = Bot(os.environ['TELEGRAM_TOKEN'])
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)
dispatcher.add_handler(MessageHandler(Filters.text, message))
dispatcher.add_error_handler(error)


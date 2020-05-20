import json
import logging
import os

from telegram import Bot, Update
from telegram.ext import Dispatcher, MessageHandler, Filters

from handlers.message import message

log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.root.setLevel(logging.getLevelName(log_level))  # type: ignore
logger = logging.getLogger(__name__)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


bot = Bot(os.environ['TELEGRAM_TOKEN'])
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)
dispatcher.add_handler(MessageHandler(Filters.text, message))
dispatcher.add_error_handler(error)


def handler(event, context):
    try:
        update = Update.de_json(json.loads(event["body"]), bot)
        logger.info('Update: {}'.format(event["body"]))
        dispatcher.process_update(update)
    except Exception as e:
        logger.error(e)
        return {"statusCode": 500}
    return {"statusCode": 200}


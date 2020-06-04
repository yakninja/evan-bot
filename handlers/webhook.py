from telegram import Update

from bot import bot, dispatcher
from helpers import *

logger = logging.getLogger(__name__)


def handler(event, context):
    """Main webhook event handler"""
    try:
        update = Update.de_json(json.loads(event["body"]), bot)
        logger.info('Update: {}'.format(event["body"]))
        dispatcher.process_update(update)
    except Exception as e:
        logger.error(e)
        return {"statusCode": 500}
    return {"statusCode": 200}


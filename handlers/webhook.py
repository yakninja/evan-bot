'''<HANDLER DESCRIPTION>'''

import json
import logging
import os

import markovify
from telegram import Bot, Update
from telegram.ext import Dispatcher, MessageHandler, Filters

log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.root.setLevel(logging.getLevelName(log_level))  # type: ignore
_logger = logging.getLogger(__name__)

# Build the Markov model for text answers
root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
with open(os.path.join(root, "corpus.txt"), encoding="utf8") as f:
    text = f.read()
text_model = markovify.Text(text, 2)


def message(update, context):
    """Reply only if spoken to"""
    from_user = update.message.from_user.first_name
    if update.message.from_user.last_name:
        from_user += ' ' + update.message.from_user.last_name
    if update.message.from_user.username:
        from_user += ' @' + update.message.from_user.username
    _logger.info('%s: "%s"', from_user, update.message.text)

    reply_text = text_model.make_short_sentence(200)
    update.message.reply_text(reply_text)


def error(update, context):
    """Log Errors caused by Updates."""
    _logger.warning('Update "%s" caused error "%s"', update, context.error)


bot = Bot(os.environ['TELEGRAM_TOKEN'])
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)
dispatcher.add_handler(MessageHandler(Filters.text, message))
dispatcher.add_error_handler(error)


def handler(event, context):
    try:
        update = Update.de_json(json.loads(event["body"]), bot)
        _logger.info('Update: {}'.format(event["body"]))
        dispatcher.process_update(update)
    except Exception as e:
        _logger.error(e)
        return {"statusCode": 500}
    return {"statusCode": 200}


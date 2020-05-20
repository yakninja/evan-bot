import os

import markovify

from helpers import *

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
    logger.info('%s: "%s"', from_user, update.message.text)

    update.message.reply_text(text_model.make_short_sentence(200))

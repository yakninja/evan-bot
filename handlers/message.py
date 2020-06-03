import random

import markovify

from bot import bot
from helpers import *
from links import *

# Build the Markov model for text answers
root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
with open(os.path.join(root, "corpus.txt"), encoding="utf8") as f:
    text = f.read()
text_model = markovify.Text(text, 2)

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
    message_text = message_text.replace('@' + bot.username.lower(), ' ').strip()
    p = re.compile(bot_name_pattern())
    message_text = p.sub(' ', message_text).strip()
    p = re.compile('\\s+')
    message_text = p.sub(' ', message_text).strip()
    return message_text


def is_spoken_to(update, context):
    """Returns true if bot is spoken to (direct mention or message starts with the bot's name)"""
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
            if m == bot.username:
                return True

    return False


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
                    stage = constants.CHAPTER_STAGE_NAMES[get_document_stage(document)]
                    reply_text = "{0}, статус: {1}".format(document['name'], stage)
                    if document['name'] in LINKS:
                        reply_text += "\nОригинал: {}".format(LINKS[document['name']])
                    if document['name'] in CHAPTER_DOCS:
                        reply_text += "\nСсылка на редактирование: {}".format(CHAPTER_DOCS[document['name']])
            else:
                reply_text = text_model.make_short_sentence(200)

    if reply_text:
        update.message.reply_text(reply_text)

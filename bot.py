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
# The polling runner supplies a disk-backed store. The legacy webhook remains usable.
history_store = None
usage_store = None


def is_allowed_update(update):
    """Fail closed before dispatching any handler for an unauthorized chat."""
    chat = getattr(update, 'effective_chat', None)
    user = getattr(update, 'effective_user', None)
    if chat is None:
        return False
    if chat.type == 'private':
        return bool(user and (user.id in globals().get('ALLOWED_USER_IDS', ()) or
                              is_admin(user)))
    if chat.type in ('group', 'supergroup'):
        return chat.id in globals().get('ALLOWED_GROUP_IDS', ())
    return False


class AllowlistedDispatcher(Dispatcher):
    def process_update(self, update):
        if is_allowed_update(update):
            return super().process_update(update)


def conversation_thread_id(message):
    # Telegram also assigns thread IDs to ordinary supergroup reply chains.
    # Only forum topics define a separate scope; a root message may have no thread ID.
    return message.message_thread_id if getattr(message, 'is_topic_message', False) else 0


def reply_history(message):
    reply = message.reply_to_message
    if not reply:
        return []
    if history_store is not None:
        try:
            history = history_store.load_chain(
                message.chat_id, conversation_thread_id(message), reply.message_id)
            if history:
                return history
        except Exception:
            logger.exception('Could not load reply-chain history')
    if reply.from_user and reply.from_user.id == bot.id and reply.text:
        return [{'role': 'assistant', 'content': reply.text}]
    return []


def remember_exchange(message, sent):
    if history_store is None:
        return
    reply = message.reply_to_message
    records = []
    if reply and reply.from_user and reply.from_user.id == bot.id and reply.text:
        records.append({'message_id': reply.message_id, 'role': 'assistant',
                        'content': reply.text})
    user_record = {'message_id': message.message_id,
                   'parent_id': reply.message_id if reply else None,
                   'role': 'user', 'content': message.text}
    if message.from_user.username:
        user_record['name'] = message.from_user.username
    records.extend([user_record, {
        'message_id': sent.message_id, 'parent_id': message.message_id,
        'role': 'assistant', 'content': sent.text}])
    try:
        history_store.save_messages(message.chat_id, conversation_thread_id(message), records)
    except Exception:
        logger.exception('Could not save reply-chain history')


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
    """Respond in private chats, to replies to this bot, and to names/mentions."""
    if update.message.chat['type'] == CHAT_TYPE_PRIVATE:
        return True

    reply = update.message.reply_to_message
    if reply and reply.from_user and reply.from_user.id == bot.id:
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
    logger.info('Greeting a new member in chat %s', update.message.chat_id)
    reply_text = random.choice(NEW_CHAT_MEMBER_GREETINGS).format(
        update.message.new_chat_members[0]['first_name'])
    if reply_text:
        update.message.reply_text(reply_text)


def limited_chatgpt(message, prompt, history):
    """Count one message after a successful paid response; reserve before calling."""
    if usage_store is None:
        logger.error('Usage store is not configured; refusing a paid API request')
        return None, False
    chat_id, message_id = message.chat_id, message.message_id
    group_id = chat_id if message.chat['type'] in ('group', 'supergroup') else None
    try:
        reason = usage_store.reserve_usage(chat_id, message_id, message.from_user.id, group_id)
    except Exception:
        logger.exception('Could not reserve daily usage')
        return None, False
    if reason == 'duplicate':
        logger.info('Ignoring a duplicate paid message')
        return None, True
    if reason:
        return 'Лимит ответов на сегодня исчерпан. Попробуй после 00:00 UTC.', True

    success_received = False

    def record_success():
        nonlocal success_received
        if not success_received:
            # Keep the reservation if recording fails after a successful request.
            success_received = True
            usage_store.mark_usage_paid(chat_id, message_id)

    try:
        return call_chatgpt(message.from_user, prompt, history=history,
                            on_success=record_success), False
    except Exception:
        logger.exception('OpenAI request or usage accounting failed')
        return None, False
    finally:
        if not success_received:
            try:
                usage_store.release_usage(chat_id, message_id)
            except Exception:
                logger.exception('Could not release an unpaid usage reservation')


def message(update, context):
    """Reply only if spoken to"""
    from_user = update.message.from_user.first_name
    if update.message.from_user.last_name:
        from_user += ' ' + update.message.from_user.last_name
    if update.message.from_user.username:
        from_user += ' @' + update.message.from_user.username
    logger.info('Message %s in chat %s', update.message.message_id, update.message.chat_id)
    reply_text = None
    remember_reply = True
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
                    history = reply_history(update.message)
                    reply_text, limited = limited_chatgpt(update.message, message_text, history)
                    if limited:
                        remember_reply = False
                    elif not reply_text:
                        remember_reply = False
                        reply_text = "Сейчас не получается ответить. Попробуй чуть позже."

    if reply_text:
        sent = update.message.reply_text(reply_text,
                                         disable_web_page_preview=True,
                                         reply_to_message_id=reply_to_message_id)
        if remember_reply:
            remember_exchange(update.message, sent)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update %s caused error: %s',
                   getattr(update, 'update_id', None), context.error)


bot = Bot(os.environ['TELEGRAM_TOKEN'])
dispatcher = AllowlistedDispatcher(bot, None, workers=0, use_context=True)

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

# -*- coding: utf-8 -*-


def help(update, context):
    """Send a message when the command /help is issued."""
    reply = """Список моих команд:
/stats - статистика перевода
/export [документ] - экспорт в текст
/executives [документ] - список пользователей, работающих над главой
/assign translation [пользователь] [документ (необязательно)] - назначить переводчика на главу или на все главы
/assign editing [пользователь] [документ (необязательно)] - назначить редактора на главу или на все главы
/revoke translation [пользователь] [документ (необязательно)] - удалить из переводчиков
/revoke editing [пользователь] [документ (необязательно)] - удалить из редакторов

Подробнее о моей работе можно почитать здесь:
https://github.com/yakninja/evan-bot
    """
    update.message.reply_text(reply)

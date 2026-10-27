from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from telegram.ext import Dispatcher
from telegram import Bot, Update

from tests.unit.test_bot_replies import bot_module


@pytest.fixture
def access(bot_module, monkeypatch):
    import helpers
    monkeypatch.setattr(bot_module, 'ALLOWED_GROUP_IDS', [-10001])
    monkeypatch.setattr(bot_module, 'ALLOWED_USER_IDS', [101])
    monkeypatch.setattr(helpers, 'ADMIN_USER_IDS', [102])
    monkeypatch.setattr(helpers, 'ADMIN_USERS', ['legacy_admin'])
    return bot_module


def update(chat_type=None, chat_id=None, user_id=999, username=None):
    chat = None if chat_type is None else SimpleNamespace(type=chat_type, id=chat_id)
    user = None if user_id is None else SimpleNamespace(id=user_id, username=username)
    return SimpleNamespace(effective_chat=chat, effective_user=user)


@pytest.mark.parametrize('chat_type', ['group', 'supergroup'])
def test_allowed_group_accepts_any_sender(access, chat_type):
    assert access.is_allowed_update(update(chat_type, -10001, 999))
    assert access.is_allowed_update(update(chat_type, -10001, None))


@pytest.mark.parametrize('chat_type', ['group', 'supergroup'])
def test_unlisted_group_rejects_even_admin(access, chat_type):
    assert not access.is_allowed_update(update(chat_type, -10002, 102))


def test_private_access_by_user_id_or_admin_id(access):
    assert access.is_allowed_update(update('private', 101, 101))
    assert access.is_allowed_update(update('private', 102, 102))
    assert not access.is_allowed_update(update('private', 103, 103))
    assert not access.is_allowed_update(update('private', 101, None))


def test_existing_username_admin_also_has_private_access(access):
    assert access.is_allowed_update(update('private', 103, 103, 'legacy_admin'))
    assert not access.is_allowed_update(update('private', 103, 103, 'not_admin'))


def test_unknown_chat_types_and_missing_chat_are_rejected(access):
    assert not access.is_allowed_update(update())
    assert not access.is_allowed_update(update('channel', -10001, 102))


def test_denied_updates_never_reach_any_handler(access, monkeypatch):
    dispatch = Mock()
    monkeypatch.setattr(Dispatcher, 'process_update', dispatch)
    for event in [update('private', 103, 103), update('group', -10002, 102), update()]:
        access.dispatcher.process_update(event)
    dispatch.assert_not_called()
    allowed = update('group', -10001, 999)
    access.dispatcher.process_update(allowed)
    dispatch.assert_called_once_with(allowed)


@pytest.mark.parametrize('chat_id,chat_type,user_id,allowed', [
    (-10001, 'supergroup', 999, True),
    (-10002, 'supergroup', 102, False),
    (101, 'private', 101, True),
    (102, 'private', 102, True),
    (103, 'private', 103, False),
])
def test_real_telegram_updates_obey_dispatch_gate(access, monkeypatch, chat_id, chat_type, user_id, allowed):
    dispatch = Mock()
    monkeypatch.setattr(Dispatcher, 'process_update', dispatch)
    event = Update.de_json({
        'update_id': 1,
        'message': {
            'message_id': 1, 'date': 0,
            'chat': {'id': chat_id, 'type': chat_type},
            'from': {'id': user_id, 'is_bot': False, 'first_name': 'Test'},
            'text': '/start',
            'entities': [{'type': 'bot_command', 'offset': 0, 'length': 6}],
        },
    }, Bot('123456:test-token'))
    access.dispatcher.process_update(event)
    assert dispatch.call_count == int(allowed)


@pytest.mark.parametrize('kind', ['assign', 'revoke', 'clear_executives'])
def test_admin_commands_use_id_and_existing_usernames(access, monkeypatch, kind):
    import importlib
    module = importlib.import_module('commands.' + kind)
    make_event = lambda user: SimpleNamespace(message=SimpleNamespace(
        from_user=user, text='/clear_executives chapter', reply_text=Mock()))
    if kind == 'clear_executives':
        mock_lookup = Mock(return_value=(None, None))
        monkeypatch.setattr(module, 'get_document_and_list_id_by_name', mock_lookup)
        for user in [SimpleNamespace(id=102, username=None),
                     SimpleNamespace(id=103, username='legacy_admin')]:
            module.clear_executives(make_event(user), None)
        assert mock_lookup.call_count == 2
        module.clear_executives(make_event(SimpleNamespace(id=101, username='someone')), None)
        assert mock_lookup.call_count == 2
    else:
        check = getattr(module, 'check_' + kind + '_permission')
        assert check(make_event(SimpleNamespace(id=102, username=None)))
        assert check(make_event(SimpleNamespace(id=103, username='legacy_admin')))
        assert not check(make_event(SimpleNamespace(id=101, username='someone')))


def test_empty_or_missing_id_lists_fail_closed(access, monkeypatch):
    import helpers
    monkeypatch.delattr(access, 'ALLOWED_GROUP_IDS')
    monkeypatch.delattr(access, 'ALLOWED_USER_IDS')
    monkeypatch.delattr(helpers, 'ADMIN_USER_IDS')
    monkeypatch.setattr(helpers, 'ADMIN_USERS', [])
    assert not access.is_allowed_update(update('group', -10001, 999))
    assert not access.is_allowed_update(update('private', 101, 101))

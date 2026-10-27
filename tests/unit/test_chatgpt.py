import importlib
from unittest.mock import Mock

import pytest
import requests


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    module = importlib.import_module('chatgpt')
    monkeypatch.setattr(module, 'CHATGPT_MODEL', 'gpt-6-luna')
    monkeypatch.setattr(module.time, 'sleep', Mock())
    return module


def response(status=200, code=None, text='Всё отлично!', headers=None):
    payload = ({'choices': [{'message': {'content': text}}]} if status == 200
               else {'error': {'code': code, 'type': 'invalid_request_error'}})
    return Mock(status_code=status, headers=headers or {}, json=Mock(return_value=payload))


def test_success_without_telegram_username(client, monkeypatch):
    post = Mock(return_value=response())
    monkeypatch.setattr(client.requests, 'post', post)
    assert client.call_chatgpt({'username': None}, 'Как дела?') == 'Всё отлично!'
    request = post.call_args.kwargs
    assert request['json']['model'] == 'gpt-6-luna'
    assert request['json']['reasoning_effort'] == 'none'
    assert request['json']['max_completion_tokens'] == 1000
    assert 'max_tokens' not in request['json']
    assert 'name' not in request['json']['messages'][-1]
    assert request['timeout'] == (2, 5)


@pytest.mark.parametrize('status,code', [
    (401, 'invalid_api_key'), (404, 'model_not_found'),
    (400, 'invalid_request_error'), (429, 'insufficient_quota'),
    (429, 'billing_hard_limit_reached'),
])
def test_permanent_errors_are_not_retried(client, monkeypatch, status, code):
    post = Mock(return_value=response(status, code))
    monkeypatch.setattr(client.requests, 'post', post)
    assert client.call_chatgpt({'username': 'tester'}, 'Как дела?') is None
    assert post.call_count == 1
    client.time.sleep.assert_not_called()


@pytest.mark.parametrize('failure', [response(429, 'rate_limit_exceeded'),
                                     response(503, 'server_is_overloaded'),
                                     requests.Timeout()])
def test_temporary_failures_can_recover(client, monkeypatch, failure):
    post = Mock(side_effect=[failure, response()])
    monkeypatch.setattr(client.requests, 'post', post)
    assert client.call_chatgpt({'username': 'tester'}, 'Как дела?') == 'Всё отлично!'
    assert post.call_count == 2
    assert {call.kwargs['json']['model'] for call in post.call_args_list} == {'gpt-6-luna'}


def test_retries_are_bounded(client, monkeypatch):
    post = Mock(return_value=response(503, 'server_is_overloaded'))
    monkeypatch.setattr(client.requests, 'post', post)
    assert client.call_chatgpt({'username': 'tester'}, 'Как дела?') is None
    assert post.call_count == 3
    assert client.time.sleep.call_count == 2


def test_long_server_backoff_stops_without_retry(client, monkeypatch):
    post = Mock(return_value=response(429, 'rate_limit_exceeded', headers={'Retry-After': '60'}))
    monkeypatch.setattr(client.requests, 'post', post)
    assert client.call_chatgpt({'username': 'tester'}, 'Как дела?') is None
    assert post.call_count == 1
    client.time.sleep.assert_not_called()


def test_filtered_response_retries_same_model(client, monkeypatch):
    post = Mock(side_effect=[response(text='Я не могу ответить'), response()])
    monkeypatch.setattr(client.requests, 'post', post)
    assert client.call_chatgpt({'username': 'tester'}, 'Как дела?') == 'Всё отлично!'
    assert post.call_count == 2


def test_success_callback_observes_every_success_even_filtered_or_malformed(client, monkeypatch):
    callback = Mock()
    post = Mock(side_effect=[response(text='Я не могу ответить'), response()])
    monkeypatch.setattr(client.requests, 'post', post)
    assert client.call_chatgpt({'username': 'tester'}, 'Как дела?', on_success=callback) == 'Всё отлично!'
    assert callback.call_count == 2
    callback.reset_mock()
    monkeypatch.setattr(client.requests, 'post', Mock(return_value=Mock(status_code=200, json=Mock(return_value={}))))
    assert client.call_chatgpt({'username': 'tester'}, 'Как дела?', on_success=callback) is None
    callback.assert_called_once()


def test_error_responses_do_not_invoke_success_callback(client, monkeypatch):
    callback = Mock()
    monkeypatch.setattr(client.requests, 'post', Mock(return_value=response(401, 'invalid_api_key')))
    assert client.call_chatgpt({'username': 'tester'}, 'Как дела?', on_success=callback) is None
    callback.assert_not_called()


def test_other_model_overrides_remain_supported(client, monkeypatch):
    monkeypatch.setattr(client, 'CHATGPT_MODEL', 'gpt-4o')
    post = Mock(return_value=response())
    monkeypatch.setattr(client.requests, 'post', post)
    assert client.call_chatgpt({'username': 'tester'}, 'Как дела?') == 'Всё отлично!'
    payload = post.call_args.kwargs['json']
    assert payload['max_tokens'] == 1000
    assert 'reasoning_effort' not in payload

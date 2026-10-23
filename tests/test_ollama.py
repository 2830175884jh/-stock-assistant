from unittest.mock import Mock

import pytest
import requests

from stock_assistant.config import load_settings
from stock_assistant.llm.client import LLMUnavailable, OllamaClient
from stock_assistant.report.builder import write_market_report
from stock_assistant.cli import run


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11435/')
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen3:4b')
    s = load_settings(tmp_path)
    s.reports_dir.mkdir(parents=True)
    return s


def response(data):
    return Mock(json=Mock(return_value=data), raise_for_status=Mock())


def test_remote_success(settings, monkeypatch):
    get = Mock(return_value=response({'models': [{'name': 'qwen3:4b'}]}))
    post = Mock(return_value=response({'message': {'content': '<think>隐藏</think>连接成功'}}))
    monkeypatch.setattr(requests, 'get', get)
    monkeypatch.setattr(requests, 'post', post)
    c = OllamaClient(settings)
    assert c.is_available()
    assert c.chat('你好') == '连接成功'
    assert get.call_args.args[0] == 'http://127.0.0.1:11435/api/tags'
    assert post.call_args.args[0] == 'http://127.0.0.1:11435/api/chat'
    assert post.call_args.kwargs['json']['stream'] is False
    assert post.call_args.kwargs['timeout'] == settings.request_timeout


@pytest.mark.parametrize('failure', [requests.ConnectionError(), requests.Timeout(), requests.HTTPError()])
def test_transport_failure(settings, monkeypatch, failure):
    monkeypatch.setattr(requests, 'get', Mock(side_effect=failure))
    monkeypatch.setattr(requests, 'post', Mock(side_effect=failure))
    c = OllamaClient(settings)
    assert not c.is_available()
    with pytest.raises(LLMUnavailable):
        c.chat('你好')


@pytest.mark.parametrize('data', [{}, None, {'models': 'bad'}, {'models': [None]}, {'models': []}, {'models': [{'name': 'other:latest'}]}])
def test_bad_tags_or_missing_model(settings, monkeypatch, data):
    monkeypatch.setattr(requests, 'get', Mock(return_value=response(data)))
    assert not OllamaClient(settings).is_available()


@pytest.mark.parametrize('data', [{}, None, {'message': None}, {'message': {'content': 42}}, {'message': {'content': '<think>only</think>'}}])
def test_bad_chat(settings, monkeypatch, data):
    monkeypatch.setattr(requests, 'post', Mock(return_value=response(data)))
    with pytest.raises(LLMUnavailable):
        OllamaClient(settings).chat('你好')


@pytest.mark.parametrize('endpoint', ['get', 'post'])
def test_invalid_json(settings, monkeypatch, endpoint):
    monkeypatch.setattr(requests, endpoint, Mock(return_value=Mock(raise_for_status=Mock(), json=Mock(side_effect=ValueError('json')))))
    with pytest.raises(LLMUnavailable):
        c = OllamaClient(settings)
        c.check() if endpoint == 'get' else c.chat('你好')


@pytest.mark.parametrize('stage', ['tags', 'chat'])
def test_report_preserves_rules_on_disconnect(settings, monkeypatch, stage):
    monkeypatch.setattr(requests, 'get', Mock(return_value=response({'models': [{'name': settings.ollama_model}]}), side_effect=requests.ConnectionError() if stage == 'tags' else None))
    monkeypatch.setattr(requests, 'post', Mock(side_effect=requests.Timeout()))
    brief = dict(trade_date='20261023', market_temperature='中性', stocks=10, up=6, down=4, up_ratio=.6, avg_pct_chg=1., amount_100m=10., limit_up_est=0, limit_down_est=0)
    text = write_market_report(settings, brief).read_text(encoding='utf-8')
    assert 'LLM 降级' in text
    assert '全市场 10 只股票' in text
    assert '免责声明' in text
    assert '## AI 解读' not in text


def test_doctor_exit_codes(settings, monkeypatch):
    monkeypatch.setattr('stock_assistant.cli.load_settings', lambda: settings)
    monkeypatch.setattr(requests, 'get', Mock(return_value=response({'models': [{'name': settings.ollama_model}]})))
    monkeypatch.setattr(requests, 'post', Mock(return_value=response({'message': {'content': '连接成功'}})))
    assert run(['--doctor']) == 0
    monkeypatch.setattr(requests, 'post', Mock(side_effect=requests.Timeout()))
    assert run(['--doctor']) == 1


@pytest.mark.parametrize('value', ['nan', 'inf', '0', '-1', 'bad'])
def test_invalid_timeout_falls_back(settings, monkeypatch, value):
    monkeypatch.setenv('OLLAMA_TIMEOUT', value)
    assert load_settings(settings.project_root).request_timeout == 60

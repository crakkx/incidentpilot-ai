import pytest
import httpx
from unittest.mock import patch, MagicMock
from app.llm.mistral_http import call_mistral_chat
from app.llm.errors import MistralRequestError, InvalidRCAOutputError
from pydantic import SecretStr
from app.core.config import settings

pytestmark = pytest.mark.no_db

def test_call_mistral_chat_success(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", SecretStr("test_key"))
    
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {
        "id": "msg-123",
        "created": 1690000000,
        "choices": [
            {
                "message": {"content": '{"result": "success"}'},
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }
    }
    
    with patch("httpx.Client.post", return_value=mock_response):
        content, metadata = call_mistral_chat(
            messages=[{"role": "user", "content": "hello"}],
            response_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            schema_name="TestSchema",
            model_name="mistral-small-latest"
        )

    assert content == '{"result": "success"}'
    assert metadata["response_id"] == "msg-123"
    assert metadata["done_reason"] == "stop"
    assert metadata["prompt_eval_count"] == 10
    assert metadata["eval_count"] == 5


def test_call_mistral_chat_missing_api_key(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", SecretStr(""))
    
    with pytest.raises(MistralRequestError, match="MISTRAL_API_KEY is not configured"):
        call_mistral_chat(
            messages=[],
            response_schema={},
            schema_name="Test",
            model_name="mistral-small"
        )


def test_call_mistral_chat_key_rotation(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", SecretStr("key1,key2"))
    
    mock_resp_429 = MagicMock(spec=httpx.Response)
    mock_resp_429.status_code = 429
    mock_resp_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests", request=MagicMock(), response=mock_resp_429
    )
    
    mock_resp_200 = MagicMock(spec=httpx.Response)
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "id": "msg-123",
        "choices": [{"message": {"content": '{"result": "success"}'}, "finish_reason": "stop"}],
        "usage": {}
    }
    
    with patch("httpx.Client.post", side_effect=[mock_resp_429, mock_resp_200]) as mock_post:
        content, _ = call_mistral_chat(
            messages=[],
            response_schema={"type": "object", "properties": {"result": {"type": "string"}}},
            schema_name="Test",
            model_name="mistral-small"
        )
        
    assert content == '{"result": "success"}'
    assert mock_post.call_count == 2


def test_call_mistral_chat_keys_exhausted(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", SecretStr("key1,key2"))
    
    mock_resp_429 = MagicMock(spec=httpx.Response)
    mock_resp_429.status_code = 429
    mock_resp_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests", request=MagicMock(), response=mock_resp_429
    )
    
    with patch("httpx.Client.post", side_effect=[mock_resp_429, mock_resp_429]) as mock_post:
        with pytest.raises(MistralRequestError, match="All API keys exhausted due to rate limits"):
            call_mistral_chat(
                messages=[],
                response_schema={"type": "object", "properties": {}},
                schema_name="Test",
                model_name="mistral-small"
            )
            
    assert mock_post.call_count == 2


def test_call_mistral_chat_invalid_json_structure(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", SecretStr("test_key"))
    
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {"id": "msg"}
    
    with patch("httpx.Client.post", return_value=mock_response):
        with pytest.raises(InvalidRCAOutputError, match="Mistral returned an unexpected API response"):
            call_mistral_chat(
                messages=[],
                response_schema={"type": "object", "properties": {}},
                schema_name="Test",
                model_name="mistral-small"
            )

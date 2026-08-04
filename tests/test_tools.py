from unittest.mock import patch, MagicMock
from app.llm.graph.tools import fetch_web_search
from app.core.config import settings
from pydantic import SecretStr

def test_fetch_web_search_success(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", SecretStr("test_tavily_key"))
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {"title": "Result 1", "url": "http://test.com", "content": "hello world", "score": 0.9}
        ]
    }
    
    with patch("httpx.post", return_value=mock_resp):
        results = fetch_web_search("query")
        
    assert len(results) == 1
    assert results[0]["title"] == "Result 1"
    assert results[0]["content"] == "hello world"

def test_fetch_web_search_fallback_offline(monkeypatch):
    # No API key
    monkeypatch.setattr(settings, "tavily_api_key", None)
    
    payload = {
        "web_search_chunks": [
            {"title": "Payload Result", "url": "http://payload.com", "content": "from payload", "score": 1.0}
        ]
    }
    
    results = fetch_web_search("query", evidence_payload=payload)
    assert len(results) == 1
    assert results[0]["title"] == "Payload Result"

def test_fetch_web_search_synthetic_fallback(monkeypatch):
    # No API key and no web_search_chunks
    monkeypatch.setattr(settings, "tavily_api_key", None)
    
    payload = {}
    
    results = fetch_web_search("query", evidence_payload=payload)
    assert len(results) == 1
    assert results[0]["title"] == "Web search fallback for: query"
    assert results[0]["score"] == 0.8

def test_fetch_web_search_error_fallback(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", SecretStr("test_tavily_key"))
    
    with patch("httpx.post", side_effect=Exception("Timeout")):
        results = fetch_web_search("query", evidence_payload={"web_search_chunks": [{"title": "Fallback", "score": 1.0}]})
        
    assert len(results) == 1
    assert results[0]["title"] == "Fallback"

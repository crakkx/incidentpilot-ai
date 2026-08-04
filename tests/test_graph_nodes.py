import pytest
import httpx
from unittest.mock import patch, MagicMock
from app.llm.graph.nodes import _invoke_node
from app.llm.graph.schemas import ExtractionResult
from app.llm.graph.state import GraphState
from app.llm.errors import InvalidRCAOutputError

pytestmark = pytest.mark.no_db

from pydantic import SecretStr
from app.core.config import settings

def test_invoke_node_success(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", SecretStr("test_key"))
    
    valid_json = '{"evidence": [], "log_anomalies": [], "metric_anomalies": [], "deployment_events": [], "entity_glossary": []}'
    
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {
        "id": "msg-123",
        "created": 1690000000,
        "choices": [{"message": {"content": valid_json}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    }

    state: GraphState = {"evidence_payload": {}, "repairs_used": 0}
    
    with patch("httpx.Client.post", return_value=mock_response):
        result = _invoke_node(
            state=state,
            node_name="extraction",
            system_prompt="sys",
            user_prompt="usr",
            schema_model=ExtractionResult,
            schema_name="rca_extraction",
            model_name="mistral-small",
            max_tokens=100,
            max_repairs=3
        )

    assert isinstance(result, ExtractionResult)
    assert len(state["call_log"]) == 1
    assert state["call_log"][0]["node"] == "extraction"
    assert state["repairs_used"] == 0


def test_invoke_node_retries_and_fails(monkeypatch):
    monkeypatch.setattr(settings, "mistral_api_key", SecretStr("test_key"))
    
    invalid_json = '{"evidence": "not a list"}'
    
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {
        "id": "msg-123",
        "created": 1690000000,
        "choices": [{"message": {"content": invalid_json}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    }

    state: GraphState = {"evidence_payload": {}, "repairs_used": 0}
    
    with patch("httpx.Client.post", return_value=mock_response):
        with pytest.raises(InvalidRCAOutputError, match="Graph node 'extraction' failed schema validation after 2 repair attempt"):
            _invoke_node(
                state=state,
                node_name="extraction",
                system_prompt="sys",
                user_prompt="usr",
                schema_model=ExtractionResult,
                schema_name="rca_extraction",
                model_name="mistral-small",
                max_tokens=100,
                max_repairs=2
            )
    
    assert len(state["call_log"]) == 3
    assert state["repairs_used"] == 2

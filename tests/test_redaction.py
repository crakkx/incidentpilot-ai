from app.core.redaction import redact_string, redact_value


def test_redacts_email():
    assert "[REDACTED_EMAIL]" in redact_string("contact ops@acme.com for help")
    assert "ops@acme.com" not in redact_string("contact ops@acme.com for help")


def test_redacts_bearer_token():
    out = redact_string("Authorization: Bearer abc123.def456-ghi")
    assert "abc123.def456-ghi" not in out
    assert "[REDACTED_TOKEN]" in out


def test_redacts_api_key_shaped_token():
    out = redact_string("used key ipk_AbCdEf1234567890AbCdEf1234567890 to call")
    assert "ipk_AbCdEf1234567890AbCdEf1234567890" not in out
    assert "[REDACTED_API_KEY]" in out


def test_redacts_connection_string():
    out = redact_string("DATABASE_URL=postgresql://user:hunter2@db.internal:5432/app")
    assert "hunter2" not in out
    assert "[REDACTED_CONNECTION_STRING]" in out


def test_leaves_normal_text_untouched():
    text = "connection pool exhausted after deploy at 14:02 UTC"
    assert redact_string(text) == text


def test_redact_value_recurses_through_nested_structures():
    payload = {
        "note": "reach me at oncall@acme.com",
        "attempts": [{"raw_output": "Bearer sometoken123456789012"}],
    }
    redacted = redact_value(payload)
    assert redacted["note"] == "reach me at [REDACTED_EMAIL]"
    assert "sometoken123456789012" not in redacted["attempts"][0]["raw_output"]

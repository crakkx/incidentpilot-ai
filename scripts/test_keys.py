import os
import httpx

keys_str = os.environ.get("MISTRAL_API_KEY", "")
keys = [k.strip() for k in keys_str.split(",") if k.strip()]

for i, k in enumerate(keys):
    resp = httpx.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"},
        json={"model": "mistral-small-latest", "messages": [{"role": "user", "content": "hi"}]}
    )
    print(f"Key {i+1} ({k[:8]}...): HTTP {resp.status_code}")

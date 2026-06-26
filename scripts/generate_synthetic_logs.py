import json
import random
from datetime import datetime, timedelta
from pathlib import Path


def main():
    output_path = Path("data/synthetic_logs.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    messages = [
        ("INFO", "GET /health completed in 4ms"),
        ("INFO", "POST /checkout started"),
        ("INFO", "Inventory reservation completed"),
        ("WARN", "Payment provider response time exceeded 1500ms"),
        ("WARN", "Database connection pool usage above 80 percent"),
        ("ERROR", "Payment authorization failed with upstream timeout"),
        ("ERROR", "Checkout confirmation failed with HTTP 504"),
    ]

    now = datetime.utcnow()
    logs = []

    for index in range(30):
        level, message = random.choice(messages)

        logs.append(
            {
                "timestamp": (now - timedelta(seconds=30 * index)).isoformat(),
                "level": level,
                "message": message,
                "source": "synthetic-generator",
                "context": {
                    "request_id": f"synthetic-req-{index:03d}",
                    "environment": "production",
                    "endpoint": "/checkout",
                },
            }
        )

    payload = {
        "service_name": "checkout-api",
        "logs": logs,
    }

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote {len(logs)} synthetic logs to {output_path}")


if __name__ == "__main__":
    main()

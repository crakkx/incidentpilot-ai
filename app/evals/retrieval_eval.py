import json
import os
import urllib.error
import urllib.request
from pathlib import Path


API_URL = os.getenv("RETRIEVE_URL", "http://localhost:8000/retrieve")
EVAL_PATH = Path("data/runbook_qa_evals.json")


def call_retrieve(question: str) -> dict:
    payload = {
        "query": question,
        "top_k": 3,
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def run_evals() -> None:
    evals = json.loads(EVAL_PATH.read_text(encoding="utf-8"))

    passed = 0

    for item in evals:
        question = item["question"]
        expected_terms = item["expected_terms"]

        response = call_retrieve(question)

        combined_text = " ".join(
            chunk["content"]
            for chunk in response["chunks"]
        ).lower()

        matched_terms = [
            term
            for term in expected_terms
            if term.lower() in combined_text
        ]

        did_pass = len(matched_terms) > 0

        if did_pass:
            passed += 1

        status = "PASS" if did_pass else "FAIL"

        print(f"[{status}] {item['id']}. {question}")
        print(f"       matched terms: {matched_terms}")

    total = len(evals)
    print()
    print(f"Retrieval eval score: {passed}/{total}")


if __name__ == "__main__":
    try:
        run_evals()
    except urllib.error.URLError as exc:
        print("Could not reach the retrieval API.")
        print("Make sure the app is running with: docker compose up --build")
        raise exc

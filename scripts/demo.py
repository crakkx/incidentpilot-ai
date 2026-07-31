import time
import requests

API_URL = "http://localhost:8000"

def run_demo():
    print("🚀 Starting RAG Retrieval Demo...")
    
    # 1. Upload the 3 runbooks
    print("\n[1] Uploading 3 Runbooks to the Knowledge Base...")
    
    runbooks = [
        {
            "name": "checkout-runbook.md",
            "content": "# Checkout Runbook\n\nCheck payment provider latency and database connection pool usage.",
            "service": "checkout-api"
        },
        {
            "name": "database-runbook.md",
            "content": "# Manual Database Runbook\n\nDatabase connection pool exhaustion can cause checkout latency. Check slow queries and active connections.",
            "service": "payments-api"
        },
        {
            "name": "needle-runbook.md",
            "content": "# Needle Runbook\n\nWhen debugging incidentpilotneedle123, check payment timeout logs and provider status.",
            "service": "payments-api"
        }
    ]
    
    for rb in runbooks:
        resp = requests.post(
            f"{API_URL}/documents/upload",
            data={
                "service_name": rb["service"],
                "document_type": "runbook",
                "severity": "high",
            },
            files={
                "file": (rb["name"], rb["content"], "text/markdown")
            }
        )
        if resp.status_code == 201:
            print(f"✅ Uploaded {rb['name']}")
        else:
            print(f"❌ Failed to upload {rb['name']}: {resp.text}")
            
    # Index the documents so pgvector creates embeddings
    print("🔄 Indexing documents for vector search...")
    idx_resp = requests.post(f"{API_URL}/documents/index")
    print(f"✅ Indexed: {idx_resp.json().get('documents_indexed')} documents")

    # 2. Create an incident that requires one of these runbooks
    print("\n[2] Creating a new incident matching 'incidentpilotneedle123'...")
    incident_payload = {
        "title": "Needle Incident Detected",
        "description": "We are seeing the specific error code incidentpilotneedle123 in the logs.",
        "environment": "production",
        "service": "payments-api"
    }
    resp = requests.post(f"{API_URL}/incidents", json=incident_payload)
    incident_id = resp.json()["id"]
    print(f"✅ Incident created with ID: {incident_id}")

    # 3. Add a log to the incident so the LLM has evidence to cite
    print("\n[3] Adding fake log evidence...")
    log_resp = requests.post(
        f"{API_URL}/logs/ingest",
        json={
            "service_name": "payments-api",
            "incident_id": incident_id,
            "logs": [
                {
                    "level": "ERROR",
                    "message": "Payment provider timeout after 30000ms. trace_id=incidentpilotneedle123",
                    "source": "payment-gateway"
                }
            ]
        }
    )
    if log_resp.status_code == 201:
        print("✅ Added payment timeout log to incident.")
    else:
        print(f"❌ Failed to add log: {log_resp.text}")

    # 4. Trigger Analysis
    print("\n[4] Triggering background analysis...")
    analyze_resp = requests.post(f"{API_URL}/incidents/{incident_id}/analyze")
    print("✅ Analysis accepted (HTTP 202) and queued in the background.")

    # 5. Poll for status
    print("\n[4] Polling the GET /analyze endpoint...")
    while True:
        status_resp = requests.get(f"{API_URL}/incidents/{incident_id}/analyze")
        if status_resp.status_code != 200:
            break
            
        data = status_resp.json()
        status = data["status"]
        progress = data.get("progress_percent", 0)
        msg = data.get("progress_message", "Working...")
        
        print(f"   ⏳ Status: {status} | Progress: {progress}% | Message: {msg}")
        
        if status == "completed":
            print("\n✅ Analysis Completed Successfully!")
            print("\n📊 Final RCA Report:")
            print(data.get("report", {}).get("incident_summary", "No summary found."))
            print("\n🎯 Recommended Actions (These should come from the needle runbook!):")
            actions = data.get("report", {}).get("recommended_actions", [])
            for action in actions:
                print(f" - {action}")
            break
        elif status in ["failed", "cancelled"]:
            print(f"\n❌ Analysis stopped with status: {status}")
            print(f"Error: {data.get('error_message')}")
            break
            
        time.sleep(2)

if __name__ == "__main__":
    run_demo()

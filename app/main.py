from fastapi import FastAPI

app = FastAPI(
    title="IncidentPilot AI",
    description="AI-powered incident analysis assistant.",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "message": "IncidentPilot AI API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "incidentpilot-ai",
        "version": "0.1.0",
    }

from prometheus_client import REGISTRY, make_asgi_app
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily
from fastapi import APIRouter
from sqlalchemy import text
from app.db.session import SessionLocal

class AnalysisJobCollector:
    def collect(self):
        db = SessionLocal()
        try:
            # Metric 1: Total Jobs
            c = GaugeMetricFamily("analysis_jobs_total", "Total number of analysis jobs", labels=["status", "model_name"])
            try:
                # To prevent Prometheus staleness (flatlining at 1 when jobs finish), 
                # we track all combinations seen and explicitly emit 0 if they drop out.
                counts = {}
                result = db.execute(text("SELECT status, model_name, COUNT(*) FROM analysis_runs GROUP BY status, model_name"))
                for row in result:
                    status = row[0] or "unknown"
                    model_name = row[1] or "unknown"
                    counts[(status, model_name)] = row[2]
                    
                # Explicitly ensure we always report "running" and "queued" as 0 if they don't exist
                # for any model that has other statuses
                models = set(m for s, m in counts.keys())
                for model in models:
                    for stat in ["queued", "running", "completed", "failed"]:
                        if (stat, model) not in counts:
                            counts[(stat, model)] = 0
                            
                for (status, model_name), count in counts.items():
                    c.add_metric([status, model_name], count)
            except Exception as e:
                pass
            yield c

            # Metric 2: Average Confidence (for completed jobs)
            conf = GaugeMetricFamily("rca_confidence_average", "Average AI confidence score of completed jobs", labels=["model_name"])
            try:
                # Map confidence strings to floats for averaging
                result = db.execute(text("""
                    SELECT model_name, AVG(
                        CASE 
                            WHEN report->>'confidence' = 'high' THEN 1.0
                            WHEN report->>'confidence' = 'medium' THEN 0.5
                            WHEN report->>'confidence' = 'low' THEN 0.0
                            ELSE 0.0
                        END
                    ) 
                    FROM analysis_runs 
                    WHERE status = 'completed' AND report IS NOT NULL 
                    AND (model_name LIKE '%mistral-small%' OR model_name LIKE '%mistral-medium%')
                    GROUP BY model_name
                """))
                for row in result:
                    model_name = row[0] or "unknown"
                    avg_conf = row[1]
                    if avg_conf is not None:
                        conf.add_metric([model_name], avg_conf)
            except Exception as e:
                pass
            yield conf

        finally:
            db.close()

# Register the custom collector
REGISTRY.register(AnalysisJobCollector())

router = APIRouter(tags=["metrics"])
metrics_app = make_asgi_app(registry=REGISTRY)

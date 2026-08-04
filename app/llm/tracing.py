"""MLflow tracing utilities.

Provides a ``mlflow_trace`` decorator factory that is a no-op when the
``MLFLOW_TRACKING_URI`` environment variable is not set (e.g. in CI or
unit-test environments where the MLflow server is not running).

Usage::

    from app.llm.tracing import mlflow_trace

    @mlflow_trace(span_type="LLM")
    def call_mistral_chat(...):
        ...
"""

import functools
import os
from typing import Any


def mlflow_trace(**decorator_kwargs: Any):
    """Conditionally apply ``mlflow.trace`` as a decorator.

    When ``MLFLOW_TRACKING_URI`` is not set, returns an identity decorator
    so the wrapped function is never touched by MLflow, avoiding any attempt
    to connect to the tracking server at import time or call time.
    """
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")

    if not tracking_uri:
        # No-op decorator — just return the function unchanged.
        def identity(fn):
            return fn

        return identity

    try:
        import mlflow

        return mlflow.trace(**decorator_kwargs)
    except ImportError:
        def identity(fn):
            return fn

        return identity

from sqlalchemy.orm import declarative_base


Base = declarative_base()


def import_models() -> None:
    import app.models.service  # noqa: F401
    import app.models.incident  # noqa: F401
    import app.models.log  # noqa: F401
    import app.models.deployment  # noqa: F401
    import app.models.document  # noqa: F401
    import app.models.document_chunk  # noqa: F401
    import app.models.analysis_run  # noqa: F401
    import app.models.metric  # noqa: F401

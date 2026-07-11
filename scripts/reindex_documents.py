import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.services.retrieval_service import reindex_all_documents  # noqa: E402


def main():
    db = SessionLocal()

    try:
        result = reindex_all_documents(db)

        print("Documents reindexed successfully.")
        print(f"Documents indexed: {result['documents_indexed']}")
        print(f"Chunks created: {result['chunks_created']}")

    finally:
        db.close()


if __name__ == "__main__":
    main()

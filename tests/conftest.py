import os
from pathlib import Path


TEST_DB_PATH = Path("test.db")

if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

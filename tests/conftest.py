import os
import sys
from pathlib import Path

# The sandbox may expose a project-level DATABASE_URL. Tests intentionally use
# an isolated SQLite engine and must not connect to that external database.
os.environ["DATABASE_URL"] = "sqlite:///./vet_connect_test_bootstrap.db"
os.environ["ENVIRONMENT"] = "testing"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

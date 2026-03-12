import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import pytest

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


SAMPLE_RESUME_1 = project_root / "data" / "samples" / "sample_resume_1.txt"
SAMPLE_RESUME_2 = project_root / "data" / "samples" / "sample_resume_2.txt"
SAMPLE_JD_1 = project_root / "data" / "samples" / "sample_jd_1.txt"


@pytest.fixture
def sample_resume_text():
    return SAMPLE_RESUME_1.read_text(encoding="utf-8")


@pytest.fixture
def sample_resume_text_2():
    return SAMPLE_RESUME_2.read_text(encoding="utf-8")


@pytest.fixture
def sample_jd_text():
    return SAMPLE_JD_1.read_text(encoding="utf-8")


# ─── Supabase In-Memory Mock ─────────────────────────────────────────────────
# This replaces the real Supabase client with an in-memory store that mimics
# the Supabase query builder API (select, eq, ilike, insert, upsert, etc.)


class _InMemoryTable:
    """Mimics supabase table query builder with in-memory data."""

    def __init__(self, storage: dict, table_name: str):
        self._storage = storage
        self._table_name = table_name
        self._data = storage.setdefault(table_name, [])
        self._id_counter = storage.setdefault(f"__{table_name}_seq", [0])
        # query state
        self._filters: list = []
        self._order_col = None
        self._order_desc = False
        self._limit_val = None
        self._select_cols = "*"
        self._is_single = False

    def _clone(self):
        t = _InMemoryTable(self._storage, self._table_name)
        t._filters = list(self._filters)
        t._order_col = self._order_col
        t._order_desc = self._order_desc
        t._limit_val = self._limit_val
        t._select_cols = self._select_cols
        t._is_single = self._is_single
        t._op = getattr(self, "_op", "select")
        t._op_data = getattr(self, "_op_data", None)
        return t

    def select(self, cols="*"):
        t = self._clone()
        t._select_cols = cols
        return t

    def eq(self, col, val):
        t = self._clone()
        t._filters.append(("eq", col, val))
        return t

    def ilike(self, col, pattern):
        t = self._clone()
        t._filters.append(("ilike", col, pattern))
        return t

    def or_(self, expr):
        t = self._clone()
        t._filters.append(("or_", expr, None))
        return t

    def order(self, col, desc=False):
        t = self._clone()
        t._order_col = col
        t._order_desc = desc
        return t

    def limit(self, n):
        t = self._clone()
        t._limit_val = n
        return t

    def single(self):
        t = self._clone()
        t._is_single = True
        return t

    def _apply_filters(self, rows):
        result = list(rows)
        for ftype, col, val in self._filters:
            if ftype == "eq":
                result = [r for r in result if r.get(col) == val]
            elif ftype == "ilike":
                pattern = val.strip("%").lower()
                result = [r for r in result if pattern in str(r.get(col, "")).lower()]
            elif ftype == "or_":
                # Simple parser for "col1.ilike.%val%,col2.ilike.%val%"
                parts = col.split(",")
                or_results = set()
                for part in parts:
                    segs = part.strip().split(".")
                    if len(segs) >= 3 and segs[1] == "ilike":
                        c = segs[0]
                        p = segs[2].strip("%").lower()
                        for i, r in enumerate(result):
                            if p in str(r.get(c, "")).lower():
                                or_results.add(i)
                result = [r for i, r in enumerate(result) if i in or_results]
        return result

    def insert(self, data):
        t = self._clone()
        t._op = "insert"
        if isinstance(data, dict):
            data = [data]
        inserted = []
        for row in data:
            row = dict(row)
            if "id" not in row or row["id"] is None:
                self._id_counter[0] += 1
                row["id"] = self._id_counter[0]
            self._data.append(row)
            inserted.append(row)
        t._op_data = inserted
        return t

    def upsert(self, data, on_conflict=None):
        t = self._clone()
        t._op = "upsert"
        if isinstance(data, dict):
            data = [data]
        upserted = []
        for row in data:
            row = dict(row)
            conflict_col = on_conflict or "id"
            existing = [r for r in self._data if r.get(conflict_col) == row.get(conflict_col)]
            if existing:
                existing[0].update(row)
                upserted.append(existing[0])
            else:
                if "id" not in row or row["id"] is None:
                    self._id_counter[0] += 1
                    row["id"] = self._id_counter[0]
                self._data.append(row)
                upserted.append(row)
        t._op_data = upserted
        return t

    def update(self, data):
        t = self._clone()
        t._op = "update"
        t._op_data = data
        return t

    def delete(self):
        t = self._clone()
        t._op = "delete"
        return t

    def execute(self):
        op = getattr(self, "_op", "select")
        resp = MagicMock()

        if op == "select":
            result = self._apply_filters(self._data)
            if self._order_col:
                result.sort(key=lambda r: r.get(self._order_col, ""), reverse=self._order_desc)
            if self._limit_val:
                result = result[: self._limit_val]
            if self._is_single:
                result = result[:1]
            resp.data = [dict(r) for r in result]

        elif op == "insert":
            resp.data = [dict(r) for r in (self._op_data or [])]

        elif op == "upsert":
            resp.data = [dict(r) for r in (self._op_data or [])]

        elif op == "update":
            matched = self._apply_filters(self._data)
            for row in matched:
                row.update(self._op_data)
            resp.data = [dict(r) for r in matched]

        elif op == "delete":
            matched = self._apply_filters(self._data)
            matched_ids = {id(r) for r in matched}
            removed = [r for r in self._data if id(r) in matched_ids]
            self._data[:] = [r for r in self._data if id(r) not in matched_ids]
            resp.data = [dict(r) for r in removed]

        return resp


class _MockSupabaseClient:
    """In-memory Supabase client mock."""

    def __init__(self):
        self._tables: dict = {}

    def table(self, name: str):
        return _InMemoryTable(self._tables, name)


@pytest.fixture(autouse=True)
def mock_supabase():
    """Auto-use fixture: patches get_supabase() with an in-memory mock for all tests."""
    client = _MockSupabaseClient()
    with patch("app.core.supabase_client.get_supabase", return_value=client), \
         patch("app.core.supabase_client._client", client):
        yield client


# ─── Auth Test Helpers ────────────────────────────────────────────────────────

TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests"


@pytest.fixture
def auth_headers():
    """Generate valid Bearer auth headers for testing authenticated endpoints."""
    with patch.object(
        __import__("app.models.config", fromlist=["config"]),
        "config",
    ) as mock_config:
        # Use the real config but override jwt_secret
        from app.models.config import config as real_config
        mock_config.__dict__.update(real_config.__dict__)
        mock_config.supabase_jwt_secret = TEST_JWT_SECRET

    payload = {
        "sub": "test-user-id-123",
        "email": "test@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

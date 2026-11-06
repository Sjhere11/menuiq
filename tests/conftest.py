from __future__ import annotations

import pytest

from menuiq import config as C
from menuiq import db, generate


@pytest.fixture(scope="module")
def short_tables():
    """Eleven days straddling the 2025-07-01 price change (fast, deterministic)."""
    orig = (C.START_DATE, C.END_DATE)
    C.START_DATE, C.END_DATE = "2025-06-25", "2025-07-05"
    try:
        yield generate.generate(seed=7)
    finally:
        C.START_DATE, C.END_DATE = orig


@pytest.fixture(scope="module")
def short_db(short_tables, tmp_path_factory):
    orig = (C.START_DATE, C.END_DATE)
    C.START_DATE, C.END_DATE = "2025-06-25", "2025-07-05"
    try:
        path = tmp_path_factory.mktemp("db") / "test.db"
        db.build_database(short_tables, path)
        yield path
    finally:
        C.START_DATE, C.END_DATE = orig

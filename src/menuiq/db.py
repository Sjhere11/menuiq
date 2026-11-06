"""Load generated tables into SQLite and expose query helpers."""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from . import config as C

log = logging.getLogger(__name__)


def _resolve(db_path: Path | None) -> Path:
    """Resolve at call time so tests can point config at a temporary location."""
    return Path(db_path) if db_path is not None else C.DB_PATH


def build_database(tables: dict[str, pd.DataFrame], db_path: Path | None = None) -> Path:
    path = _resolve(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    dates = pd.date_range(C.START_DATE, C.END_DATE, freq="D")
    dim_date = pd.DataFrame(
        {
            "date_key": dates.strftime("%Y-%m-%d"),
            "year": dates.year,
            "month": dates.month,
            "dow": dates.dayofweek,
            "is_weekend": (dates.dayofweek >= 5).astype(int),
        }
    )
    orders = tables["fact_orders"].copy()
    orders["order_ts"] = orders["order_ts"].dt.strftime("%Y-%m-%d %H:%M:%S")
    orders["order_date"] = orders["order_date"].dt.strftime("%Y-%m-%d")
    with closing(sqlite3.connect(path)) as con:
        con.executescript((C.SQL_DIR / "schema.sql").read_text())
        dim_date.to_sql("dim_date", con, if_exists="append", index=False)
        tables["dim_item"].to_sql("dim_item", con, if_exists="append", index=False)
        orders.to_sql("fact_orders", con, if_exists="append", index=False)
        tables["fact_order_items"].to_sql("fact_order_items", con, if_exists="append", index=False)
        con.commit()
    log.info("database written to %s", path)
    return path


def query(sql: str, db_path: Path | None = None, params: tuple = ()) -> pd.DataFrame:
    with closing(sqlite3.connect(_resolve(db_path))) as con:
        return pd.read_sql_query(sql, con, params=params)


def run_sql_file(path: Path, db_path: Path | None = None) -> list[pd.DataFrame]:
    """Run each ';'-terminated statement in a .sql file and return the result sets."""
    text = "\n".join(line for line in path.read_text().splitlines() if not line.strip().startswith("--"))
    return [query(stmt, db_path) for stmt in (s.strip() for s in text.split(";")) if stmt]

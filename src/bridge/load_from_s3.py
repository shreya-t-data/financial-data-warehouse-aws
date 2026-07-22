"""
Bridge script: S3 (bronze/raw landing zone) -> local Postgres raw schema.

Idempotent -- tracks loaded S3 object keys in raw.loaded_files so
re-running never duplicates data. Upserts on natural keys so a
re-processed file (or a corrected re-run) never creates duplicate rows.
"""

import json
import logging
import os

import boto3
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

AWS_PROFILE = os.environ.get("AWS_PROFILE", "financial-warehouse")
S3_BUCKET = os.environ["S3_BUCKET"]

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432"),
    "dbname": os.environ.get("DB_NAME", "findw"),
    "user": os.environ.get("DB_USER", "shreya"),
    "password": os.environ["POSTGRES_PASSWORD"],
}

session = boto3.Session(profile_name=AWS_PROFILE)
s3 = session.client("s3")


DDL = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.loaded_files (
    s3_key      TEXT PRIMARY KEY,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.sec_companies (
    cik              BIGINT PRIMARY KEY,
    ticker           TEXT NOT NULL,
    company_name     TEXT,
    sic              TEXT,
    sic_description  TEXT,
    former_names     JSONB,
    fetched_at       TIMESTAMPTZ,
    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.stock_prices (
    ticker      TEXT NOT NULL,
    date        DATE NOT NULL,
    open        NUMERIC,
    high        NUMERIC,
    low         NUMERIC,
    close       NUMERIC,
    volume      BIGINT,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker, date)
);
"""


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()


def list_new_keys(conn, prefix: str) -> list[str]:
    """List every object under a prefix, minus ones already recorded as loaded."""
    with conn.cursor() as cur:
        cur.execute("SELECT s3_key FROM raw.loaded_files")
        already_loaded = {row[0] for row in cur.fetchall()}

    paginator = s3.get_paginator("list_objects_v2")
    all_keys = []
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            all_keys.append(obj["Key"])

    new_keys = [k for k in all_keys if k not in already_loaded]
    logger.info("Prefix %s: %d total objects, %d new", prefix, len(all_keys), len(new_keys))
    return new_keys


def mark_loaded(conn, key: str):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO raw.loaded_files (s3_key) VALUES (%s) ON CONFLICT DO NOTHING",
            (key,),
        )
    conn.commit()


def load_sec_companies(conn, key: str) -> int:
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    records = json.loads(obj["Body"].read().decode("utf-8"))

    rows = [
        (
            r["cik"],
            r["ticker"],
            r.get("company_name"),
            str(r.get("sic")) if r.get("sic") is not None else None,
            r.get("sic_description"),
            json.dumps(r.get("former_names", [])),
            r.get("fetched_at"),
        )
        for r in records
    ]

    if not rows:
        logger.warning("No records parsed from %s", key)
        return 0

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO raw.sec_companies
                (cik, ticker, company_name, sic, sic_description, former_names, fetched_at)
            VALUES %s
            ON CONFLICT (cik) DO UPDATE SET
                ticker = EXCLUDED.ticker,
                company_name = EXCLUDED.company_name,
                sic = EXCLUDED.sic,
                sic_description = EXCLUDED.sic_description,
                former_names = EXCLUDED.former_names,
                fetched_at = EXCLUDED.fetched_at,
                loaded_at = now()
            """,
            rows,
        )
    conn.commit()
    logger.info("Upserted %d rows into raw.sec_companies from %s", len(rows), key)
    return len(rows)


def load_stock_prices(conn, key: str) -> int:
    # key looks like: bronze/alpha_vantage/dt=2026-07-22/NVDA.json
    ticker = key.split("/")[-1].replace(".json", "")

    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    series = json.loads(obj["Body"].read().decode("utf-8"))

    rows = []
    for date_str, values in series.items():
        try:
            rows.append((
                ticker,
                date_str,
                float(values["1. open"]),
                float(values["2. high"]),
                float(values["3. low"]),
                float(values["4. close"]),
                int(values["5. volume"]),
            ))
        except (KeyError, ValueError) as e:
            logger.warning("Skipping malformed entry in %s for date %s: %s (%s)", key, date_str, values, e)

    if not rows:
        logger.warning("No valid rows parsed from %s", key)
        return 0

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO raw.stock_prices (ticker, date, open, high, low, close, volume)
            VALUES %s
            ON CONFLICT (ticker, date) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                loaded_at = now()
            """,
            rows,
        )
    conn.commit()
    logger.info("Upserted %d rows into raw.stock_prices from %s", len(rows), key)
    return len(rows)


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    ensure_schema(conn)

    sec_keys = list_new_keys(conn, "bronze/sec_edgar/")
    for key in sec_keys:
        rows_loaded = load_sec_companies(conn, key)
        if rows_loaded:
            mark_loaded(conn, key)

    price_keys = list_new_keys(conn, "bronze/alpha_vantage/")
    for key in price_keys:
        rows_loaded = load_stock_prices(conn, key)
        if rows_loaded:
            mark_loaded(conn, key)

    conn.close()
    logger.info("Bridge run complete: %d SEC file(s), %d price file(s) processed", len(sec_keys), len(price_keys))


if __name__ == "__main__":
    main()
"""
AWS Lambda: stooq_ingest

Downloads daily OHLCV (open/high/low/close/volume) price history for a
fixed basket of tickers from Stooq's free CSV endpoint, and lands each
ticker's data in S3 as bronze/raw data.

Uses only the Python standard library + boto3 -- no external
dependencies, so no Lambda layer needed.
"""

import csv
import io
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

STOOQ_URL = "https://stooq.com/q/d/l/?s={ticker}.us&i=d"


def _fetch_csv_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "financial-data-warehouse-aws"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8")


def _fetch_ticker_csv(ticker: str) -> str:
    return _fetch_csv_text(STOOQ_URL.format(ticker=ticker.lower()))


def _count_data_rows(csv_text: str) -> int:
    reader = csv.reader(io.StringIO(csv_text))
    next(reader, None) # skip header row
    return sum(1 for _ in reader)


def handler(event, context):
    tickers = os.environ.get("TICKERS", "").split(",")
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    bucket = os.environ["S3_BUCKET"]

    if not tickers:
        raise ValueError("TICKERS environment variable is empty or unset")

    logger.info("Starting Stooq ingest for %d tickers: %s", len(tickers), tickers)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    written = 0

    for ticker in tickers:
        try:
            csv_text = _fetch_ticker_csv(ticker)
        except urllib.error.HTTPError as e:
            logger.error("Failed to fetch Stooq data for %s: %s", ticker, e)
            continue

        # Stooq returns a near-empty CSV (just a header, or a literal
        # "No data" body) for a bad/renamed/delisted ticker instead of
        # a proper HTTP error -- so we chech row count, not just status.
        row_count = _count_data_rows(csv_text)
        if row_count == 0:
            logger.warning("No rows returned for %s - possibly an invalid or renamed ticker, skipping", ticker)
            continue
        
        key = f"bronze/stooq/dt={today}/{ticker}.csv"
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=csv_text.encode("utf-8"),
            ContentType="text/csv",
        )
        written += 1
        logger.info ("Wrote %d rows for %s to s3://%s/%s", row_count, ticker, bucket, key)

    return {
        "statusCode": 200,
        "tickers_written": written,
    }
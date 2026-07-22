"""
AWS Lambda: alpha_vantage_ingest

Downloads daily OHLCV (open/high/low/close/volume) price history for a
fixed basket of tickers from Alpha Vantage's free TIME_SERIES_DAILY API,
and lands each ticker's data in S3 as bronze/raw data.

Free tier: 25 requests/day. We use exactly 1 request per ticker per run
(8 tickers = 8 requests/day), well within the limit.

Uses only the Python standard library + boto3 -- no external
dependencies, so no Lambda layer needed.
"""

import json
import logging
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

ALPHA_VANTAGE_URL = (
    "https://www.alphavantage.co/query"
    "?function=TIME_SERIES_DAILY&symbol={ticker}&outputsize=compact&apikey={api_key}"
)


def _fetch_ticker_json(ticker: str, api_key: str) -> dict:
    url = ALPHA_VANTAGE_URL.format(ticker=ticker, api_key=api_key)
    req = urllib.request.Request(url, headers={"User-Agent": "financial-data-warehouse-aws"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def handler(event, context):
    tickers = os.environ.get("TICKERS", "").split(",")
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    bucket = os.environ["S3_BUCKET"]
    api_key = os.environ["ALPHA_VANTAGE_API_KEY"]

    if not tickers:
        raise ValueError("TICKERS environment variable is empty or unset")

    logger.info("Starting Alpha Vantage ingest for %d tickers: %s", len(tickers), tickers)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    written = 0

    for i, ticker in enumerate(tickers):
        try:
            data = _fetch_ticker_json(ticker, api_key)
        except urllib.error.HTTPError as e:
            logger.error("Failed to fetch Alpha Vantage data for %s: %s", ticker, e)
            continue

        # Alpha Vantage returns a 200 with an "Error Message" or "Note" key
        # (rate limit / bad symbol) instead of a proper HTTP error -- check
        # for the real payload key before trusting the response.
        series = data.get("Time Series (Daily)")
        if series is None:
            logger.warning(
                "No time series data for %s — API responded with: %s",
                ticker, {k: v for k, v in data.items() if k != "Time Series (Daily)"}
            )
            continue

        key = f"bronze/alpha_vantage/dt={today}/{ticker}.json"
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(series).encode("utf-8"),
            ContentType="application/json",
        )
        written += 1
        logger.info("Wrote %d days of data for %s to s3://%s/%s", len(series), ticker, bucket, key)

        # Free tier is rate-limited per-minute too (5 calls/min), not just
        # per-day -- a short pause keeps us well clear of that even though
        # 8 calls in a Lambda invocation would likely be fine regardless.
        if i < len(tickers) - 1:
            time.sleep(2)

    return {
        "statusCode": 200,
        "tickers_written": written,
    }
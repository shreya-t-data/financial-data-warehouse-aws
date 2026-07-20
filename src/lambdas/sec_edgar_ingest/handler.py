"""
AWS Lambda: sec_edgar_ingest

Pulls company classification data (SIC code, name, former names) from 
SEC EDGAR's free public JSON APIs for a fixed basket of tickers, and
lands the result in S3 as bronze/raw data.

Uses only the Python standard library + boto3 (preinstalled in the
Lambda runtime) -- no external dependencies, so no Lambda layer needed.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"


def _user_agent() -> str:
    contact_email = os.environ.get("CONTACT_EMAIL", "unknown@example.com")
    return f"financial-data-warehouse-aws {contact_email}"


def _fetch_json(url: str) -> dict:
    """ GET a URL and parse the JSON response, with SEC's required User-Agent header."""
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _build_ticker_to_cik_map() -> dict:
    """
    company_tickers.json looks like:
    {"0}: {"cik_str": "0000000000", "ticker": "AAPL", "title": "Apple Inc."}, "1": {...}, ... }
    Returns {ticker: cik_int}.
    """
    raw = _fetch_json(TICKER_MAP_URL)
    return {entry["ticker"]: entry["cik_str"] for entry in raw.values()}


def _fetch_company_submission(cik: int) -> dict:
    return _fetch_json(SUBMISSIONS_URL.format(cik=cik))


def handler(event, context):
    tickers = os.environ.get("TICKERS", "").split(",")
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    bucket = os.environ["S3_BUCKET"]

    if not tickers:
        raise ValueError("TICKERS environment variable is empty or unset")

    logger.info("Starting SEC EDGAR ingest for %d tickers: %s", len(tickers), tickers)

    ticker_to_cik = _build_ticker_to_cik_map()

    results = []
    fetched_at = datetime.now(timezone.utc).isoformat()

    for ticker in tickers:
        cik = ticker_to_cik.get(ticker)
        if cik is None:
            logger.warning("Ticker %s not found in SEC's company_tickers.json - skipping", ticker)
            continue

        try:
            submission = _fetch_company_submission(cik)
        except urllib.error.HTTPError as e:
            logger.error("Failed to fetch submission for %s (CIK %s): %s", ticker, cik, e)
            continue

        results.append({
            "cik": cik,
            "ticker": ticker,
            "company_name": submission.get("name"),
            "sic": submission.get("sic"),
            "sic_description": submission.get("sicDescription"),
            "former_names": submission.get("formerNames", []),
            "fetched_at": fetched_at
        })
        logger.info("Fetched %s (CIK %s): SIC %s - %s", ticker, cik, submission.get("sic"), submission.get("sicDescription"))
    

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"bronze/sec_edgar/dt={today}/companies.json"

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(results, indent=2).encode("utf-8"),
        ContentType="application/json",
    )

    logger.info("Wrote %d company records to s3://%s/%s", len(results), bucket, key)

    return {
        "statusCode": 200,
        "companies_fetched": len(results),
        "s3_key": key,
    }
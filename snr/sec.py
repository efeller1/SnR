"""SEC EDGAR access: ticker map, company submissions, and XBRL company facts.

Every XBRL fact carries the date it was *filed*, which is what makes the
fundamentals point-in-time: a fact is only visible to a screen dated on or
after its filing date.
"""
from __future__ import annotations

import io
import json
import os
import threading
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

from .config import CACHE_DIR

BULK_FACTS_URL = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

REVENUE_TAGS = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
    "RevenuesNetOfInterestExpense",
)
COST_TAGS = (
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "CostOfGoodsSold",
    "CostOfServices",
    "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
)
GROSS_PROFIT_TAGS = ("GrossProfit",)
OTHER_TAGS = (
    "NetIncomeLoss",
    "NetCashProvidedByUsedInOperatingActivities",
    "CashAndCashEquivalentsAtCarryingValue",
    "CommonStockSharesOutstanding",
)
DEI_TAGS = ("EntityCommonStockSharesOutstanding",)
KEEP_TAGS = frozenset(REVENUE_TAGS + COST_TAGS + GROSS_PROFIT_TAGS + OTHER_TAGS + DEI_TAGS)
FACT_COLUMNS = ["cik", "tag", "start", "end", "val", "form", "filed", "accn"]


class SecClient:
    """Rate-limited (<10 req/s, per SEC fair-access policy) cached client."""

    def __init__(self, cache_dir: Path = CACHE_DIR / "sec", user_agent: str | None = None):
        ua = user_agent or os.environ.get("SEC_USER_AGENT")
        if not ua:
            raise RuntimeError("Set SEC_USER_AGENT, e.g. 'Your Name your@email.com' (required by SEC).")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": ua, "Accept-Encoding": "gzip, deflate"})
        self._lock = threading.Lock()
        self._last = 0.0

    def _get(self, url: str, stream: bool = False) -> requests.Response:
        for attempt in range(5):
            with self._lock:
                wait = 0.12 - (time.monotonic() - self._last)
                if wait > 0:
                    time.sleep(wait)
                self._last = time.monotonic()
            resp = self.session.get(url, timeout=60, stream=stream)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 404:
                resp.raise_for_status()
            time.sleep(2 ** attempt)
        resp.raise_for_status()
        return resp

    def get_json(self, url: str, cache_name: str | None = None, max_age_days: float | None = None) -> dict:
        path = self.cache_dir / cache_name if cache_name else None
        if path and path.exists():
            age = (time.time() - path.stat().st_mtime) / 86400
            if max_age_days is None or age <= max_age_days:
                return json.loads(path.read_text())
        data = self._get(url).json()
        if path:
            path.write_text(json.dumps(data))
        return data

    def download(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part")
        with self._get(url, stream=True) as resp, open(tmp, "wb") as fh:
            for chunk in resp.iter_content(1 << 20):
                fh.write(chunk)
        tmp.replace(dest)
        return dest

    # --- high-level helpers -------------------------------------------------

    def ticker_map(self, exchanges: tuple) -> pd.DataFrame:
        """One primary ticker per CIK among currently listed common stocks.

        EDGAR has no historical ticker map, so this is the *current* listing
        set; companies acquired or delisted since a backtest date are missing
        (survivorship bias, reported in the validation output).
        """
        raw = self.get_json(TICKERS_URL, "company_tickers_exchange.json", max_age_days=7)
        df = pd.DataFrame(raw["data"], columns=raw["fields"])
        df = df[df["exchange"].isin(exchanges)].copy()
        df["has_dash"] = df["ticker"].str.contains("-")
        df["tlen"] = df["ticker"].str.len()
        df = df.sort_values(["cik", "has_dash", "tlen"]).drop_duplicates("cik")
        return df[["cik", "ticker", "name", "exchange"]].reset_index(drop=True)

    def submissions(self, cik: int) -> dict:
        data = self.get_json(SUBMISSIONS_URL.format(cik=cik), f"sub_{cik}.json", max_age_days=30)
        return {
            "cik": cik,
            "name": data.get("name"),
            "sic": int(data["sic"]) if str(data.get("sic") or "").isdigit() else None,
            "sic_description": data.get("sicDescription"),
            "tickers": data.get("tickers", []),
            "exchanges": data.get("exchanges", []),
        }

    def company_facts(self, cik: int) -> pd.DataFrame:
        data = self.get_json(FACTS_URL.format(cik=cik), f"facts_{cik}.json", max_age_days=7)
        return pd.DataFrame(_extract_rows(data), columns=FACT_COLUMNS).pipe(_typed)


def _extract_rows(data: dict) -> list[tuple]:
    cik = int(data.get("cik") or 0)
    rows = []
    for taxonomy in ("us-gaap", "dei"):
        for tag, body in (data.get("facts", {}).get(taxonomy) or {}).items():
            if tag not in KEEP_TAGS:
                continue
            for unit, facts in body.get("units", {}).items():
                if unit not in ("USD", "shares"):
                    continue
                for f in facts:
                    rows.append((cik, tag, f.get("start"), f.get("end"), f.get("val"),
                                 f.get("form"), f.get("filed"), f.get("accn")))
    return rows


def _typed(df: pd.DataFrame) -> pd.DataFrame:
    for col in ("start", "end", "filed"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["val"] = pd.to_numeric(df["val"], errors="coerce")
    df["cik"] = df["cik"].astype("int64")
    df["tag"] = df["tag"].astype("category")
    df["form"] = df["form"].astype("category")
    return df.dropna(subset=["end", "filed", "val"])


def build_facts_table(client: SecClient, out_path: Path = CACHE_DIR / "facts.parquet",
                      refresh: bool = False) -> Path:
    """Download EDGAR's bulk companyfacts.zip and reduce it to the tags we use."""
    zip_path = CACHE_DIR / "companyfacts.zip"
    if refresh or not zip_path.exists():
        client.download(BULK_FACTS_URL, zip_path)
    frames, rows = [], []
    with zipfile.ZipFile(zip_path) as zf:
        for i, name in enumerate(zf.namelist()):
            with zf.open(name) as fh:
                try:
                    data = json.load(io.TextIOWrapper(fh, encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
            rows.extend(_extract_rows(data))
            if len(rows) > 2_000_000:
                frames.append(pd.DataFrame(rows, columns=FACT_COLUMNS).pipe(_typed))
                rows = []
            if i % 2000 == 0:
                print(f"  parsed {i} company files")
    frames.append(pd.DataFrame(rows, columns=FACT_COLUMNS).pipe(_typed))
    facts = pd.concat(frames, ignore_index=True)
    for col in ("tag", "form"):
        facts[col] = facts[col].astype(str).astype("category")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    facts.to_parquet(out_path, index=False)
    return out_path


def load_facts(path: Path = CACHE_DIR / "facts.parquet") -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run `python -m snr build-facts` first.")
    return pd.read_parquet(path)

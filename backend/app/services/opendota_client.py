"""
Shared OpenDota API client.

Centralizes HTTP request handling, daily quota accounting, and rate limiting
for every consumer of the OpenDota API (match fetcher, player mapper, live
career endpoint, hero stats verification, bulk discovery).

Quota model (anonymous tier: 2,950 calls/day, 60 calls/min):
  - One shared daily budget split into labelled buckets:
      fetcher  -> GET /matches/{id}   (largest slice: match details are priority)
      mapper   -> GET /search         (capped small; local index maps most names)
      other    -> heroes, heroStats, career, discovery
  - A call is counted toward the shared total only once a server response is
    received (non-429). Retries for 429 / network errors do not count.

Rate limiting:
  - Minimum interval between calls (~1.11s -> ~55 req/min, under the 60/min
    anonymous cap) with small jitter to avoid lockstep bursts.
  - Exponential backoff on 429, honoring the Retry-After header when present.
"""

import json
import os
import random
import time
import logging
import threading
from datetime import date, datetime, timezone

import requests

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

logger = logging.getLogger("opendota_client")

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
QUOTA_FILE = os.path.join(DATA_DIR, "api_quota.json")

OPENDOTA_BASE = os.getenv("OPENDOTA_BASE", "https://api.opendota.com/api")
OPENDOTA_TIMEOUT = int(os.getenv("OPENDOTA_TIMEOUT", "12"))
DAILY_LIMIT = int(os.getenv("OPENDOTA_DAILY_LIMIT", "2950"))
MIN_INTERVAL = float(os.getenv("OPENDOTA_MIN_INTERVAL", "1.11"))

# Soft caps used for reporting and per-bucket throttling.
# Mapper needs stay small: the pro-player index + match payload mining map
# most names locally, so /search is only a fallback. The fetcher gets the
# rest so match details can be backfilled as fast as the daily budget allows.
OTHER_QUOTA = max(100, DAILY_LIMIT // 20)       # hard cap for live/utility calls
MAPPER_QUOTA = min(int(os.getenv("OPENDOTA_MAPPER_QUOTA", "150")), DAILY_LIMIT // 4)
FETCHER_QUOTA = max(0, DAILY_LIMIT - MAPPER_QUOTA - OTHER_QUOTA)

BUCKETS = ("fetcher", "mapper", "other")
_BUCKET_CAPS = {"fetcher": FETCHER_QUOTA, "mapper": MAPPER_QUOTA, "other": OTHER_QUOTA}

_session_lock = threading.Lock()
_session_local = threading.local()
_last_call_time = 0.0


def _get_session():
    """Return a thread-local requests.Session.

    Worker threads fetch concurrently, so each thread keeps its own session
    (requests.Session is not guaranteed safe to share across threads).
    """
    session = getattr(_session_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update({"Accept": "application/json"})
        _session_local.session = session
    return session


# ─── Quota persistence (fcntl-locked) ───────────────────────────────────


def _default_quota():
    return {
        "date": None,
        "fetcher_calls": 0,
        "mapper_calls": 0,
        "other_calls": 0,
        "daily_limit": DAILY_LIMIT,
    }


def _get_quota():
    if os.path.exists(QUOTA_FILE):
        with open(QUOTA_FILE, "r") as f:
            if _HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_SH)
            try:
                quota = json.load(f)
                quota.setdefault("other_calls", 0)
                quota["daily_limit"] = DAILY_LIMIT
                return quota
            finally:
                if _HAS_FCNTL:
                    fcntl.flock(f, fcntl.LOCK_UN)
    return _default_quota()


def _save_quota(quota):
    with open(QUOTA_FILE, "w") as f:
        if _HAS_FCNTL:
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(quota, f, indent=2)
        finally:
            if _HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_UN)


def get_quota():
    quota = _get_quota()
    return reset_quota_if_new_day(quota)


def reset_quota_if_new_day(quota):
    today = date.today().isoformat()
    if quota.get("date") != today:
        quota["date"] = today
        quota["fetcher_calls"] = 0
        quota["mapper_calls"] = 0
        quota["other_calls"] = 0
        _save_quota(quota)
        logger.info(f"New day ({today}), quota reset.")
    return quota


def _used(quota):
    return (
        quota.get("fetcher_calls", 0)
        + quota.get("mapper_calls", 0)
        + quota.get("other_calls", 0)
    )


def _bump(bucket):
    quota = _get_quota()
    quota = reset_quota_if_new_day(quota)
    key = f"{bucket}_calls"
    quota[key] = quota.get(key, 0) + 1
    _save_quota(quota)


def quota_remaining(bucket="other"):
    if bucket not in _BUCKET_CAPS:
        bucket = "other"
    quota = _get_quota()
    quota = reset_quota_if_new_day(quota)
    key = f"{bucket}_calls"
    bucket_used = quota.get(key, 0)
    cap = _BUCKET_CAPS[bucket]
    return max(0, min(cap - bucket_used, DAILY_LIMIT - _used(quota)))


# ─── Rate limiting ──────────────────────────────────────────────────────


def _rate_limit():
    global _last_call_time
    with _session_lock:
        elapsed = time.monotonic() - _last_call_time
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed + random.uniform(0, 0.15))
        _last_call_time = time.monotonic()


def _retry_after(resp):
    value = resp.headers.get("Retry-After")
    if value:
        try:
            return max(0, float(value))
        except ValueError:
            pass
    return None


# ─── Public request entry point ─────────────────────────────────────────


def api_get(path, params=None, bucket="other", max_retries=2, timeout=OPENDOTA_TIMEOUT):
    """GET an OpenDota endpoint under shared quota + rate limiting.

    Returns a requests.Response, or None when the bucket/daily quota is
    exhausted or the request fails after max_retries. Callers must treat
    404/5xx via the returned status code.
    """
    if bucket not in _BUCKET_CAPS:
        bucket = "other"
    if quota_remaining(bucket) <= 0:
        logger.info(f"Quota exhausted for bucket '{bucket}'. Skipping {path}.")
        return None

    url = f"{OPENDOTA_BASE}{path}"
    session = _get_session()
    last_error = None

    for attempt in range(max_retries):
        _rate_limit()
        try:
            resp = session.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:
                wait = _retry_after(resp)
                if wait is None:
                    wait = min(60 * (2 ** attempt), 120)
                logger.warning(f"Rate limited on {path}. Sleeping {wait:.0f}s.")
                time.sleep(wait)
                continue
            _bump(bucket)
            return resp
        except requests.exceptions.RequestException as e:
            last_error = e
            wait = min(3 * (2 ** attempt), 15)
            logger.warning(
                f"Request error on {path}: {e}. Retry {attempt + 1}/{max_retries} in {wait}s."
            )
            time.sleep(wait)

    logger.error(f"Failed {path} after {max_retries} attempts: {last_error}")
    return None

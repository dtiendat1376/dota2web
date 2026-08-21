"""
Hero stats cross-validation against OpenDota /heroStats endpoint.

Fetches pro-level hero statistics once per day, compares with local tournament data,
and stores results in the verification_results table.
"""

import json
import os
import sqlite3
import logging
from datetime import datetime, timezone, timedelta

import requests

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "dota2.db")
HERO_STATS_CACHE = os.path.join(DATA_DIR, "hero_stats_cache.json")

OPENDOTA_BASE = "https://api.opendota.com/api"
CACHE_TTL = 86400  # 24 hours
MIN_PICKS = 5
PRO_MIN_PICKS = 20
WARN_THRESHOLD = 0.10
FAIL_THRESHOLD = 0.20

logger = logging.getLogger("verify_hero_stats")


def _load_cache():
    if not os.path.exists(HERO_STATS_CACHE):
        return None
    try:
        with open(HERO_STATS_CACHE, "r") as f:
            cached = json.load(f)
        fetched_at = datetime.fromisoformat(cached["fetched_at"])
        if (datetime.now(timezone.utc) - fetched_at).total_seconds() < CACHE_TTL:
            return cached["data"]
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    return None


def _save_cache(data):
    with open(HERO_STATS_CACHE, "w") as f:
        json.dump({
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }, f)


def ensure_hero_pro_columns(conn=None):
    """Idempotently add pro_pick/pro_win/pro_ban columns to the heroes table."""
    close = conn is None
    if close:
        conn = sqlite3.connect(DB_PATH)
    try:
        for col in ("pro_pick", "pro_win", "pro_ban"):
            try:
                conn.execute(f"ALTER TABLE heroes ADD COLUMN {col} INTEGER")
            except sqlite3.OperationalError:
                pass
        conn.commit()
    finally:
        if close:
            conn.close()


def update_hero_pro_stats(hero_stats):
    """Persist pro pick/win/ban counts from /heroStats into the heroes table."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    ensure_hero_pro_columns(conn)
    updated = 0
    for h in hero_stats:
        hid = h.get("id")
        if hid is None:
            continue
        cur.execute(
            "UPDATE heroes SET pro_pick = ?, pro_win = ?, pro_ban = ? WHERE hero_id = ?",
            (h.get("pro_pick", 0) or 0,
             h.get("pro_win", 0) or 0,
             h.get("pro_ban", 0) or 0,
             hid),
        )
        if cur.rowcount:
            updated += 1
    conn.commit()
    conn.close()
    logger.info(f"Updated pro stats for {updated} heroes.")
    return updated


def fetch_hero_stats():
    cached = _load_cache()
    if cached is not None:
        logger.info("Using cached hero stats.")
        return cached

    logger.info("Fetching /heroStats from OpenDota...")
    resp = requests.get(f"{OPENDOTA_BASE}/heroStats", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    _save_cache(data)
    logger.info(f"Fetched hero stats for {len(data)} heroes.")
    return data


def _get_local_hero_stats():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT mps.hero_id,
               COUNT(*) as picks,
               SUM(mps.win) as wins
        FROM match_player_stats mps
        JOIN match_details md ON mps.dota_game_id = md.dota_game_id
        WHERE mps.hero_id IS NOT NULL
        GROUP BY mps.hero_id
        HAVING picks >= ?
    """, (MIN_PICKS,))
    rows = cur.fetchall()
    conn.close()
    return {row[0]: {"picks": row[1], "wins": row[2] or 0} for row in rows}


def _get_hero_name_map():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT hero_id, localized_name FROM heroes")
    rows = cur.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def run_hero_verification():
    hero_stats = fetch_hero_stats()
    update_hero_pro_stats(hero_stats)
    local_stats = _get_local_hero_stats()
    hero_names = _get_hero_name_map()

    pro_lookup = {}
    for h in hero_stats:
        hid = h["id"]
        pro_pick = h.get("pro_pick", 0) or 0
        pro_win = h.get("pro_win", 0) or 0
        if pro_pick >= PRO_MIN_PICKS:
            pro_lookup[hid] = {
                "pro_pick": pro_pick,
                "pro_win": pro_win,
                "pro_wr": pro_win / pro_pick,
            }

    results = []
    for hero_id, local in local_stats.items():
        if hero_id not in pro_lookup:
            continue
        pro = pro_lookup[hero_id]
        local_wr = local["wins"] / local["picks"]
        deviation = abs(local_wr - pro["pro_wr"])

        if deviation <= WARN_THRESHOLD:
            status = "pass"
        elif deviation <= FAIL_THRESHOLD:
            status = "warn"
        else:
            status = "fail"

        results.append({
            "hero_id": hero_id,
            "hero_name": hero_names.get(hero_id, f"Hero {hero_id}"),
            "expected_value": pro["pro_wr"],
            "actual_value": local_wr,
            "deviation": deviation,
            "status": status,
            "sample_size": local["picks"],
        })

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM verification_results")
    for r in results:
        cur.execute("""
            INSERT INTO verification_results
                (check_type, entity_id, entity_name, expected_value, actual_value,
                 deviation, status, sample_size, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "hero_win_rate",
            r["hero_id"],
            r["hero_name"],
            r["expected_value"],
            r["actual_value"],
            r["deviation"],
            r["status"],
            r["sample_size"],
            now,
        ))
    conn.commit()
    conn.close()

    pass_count = sum(1 for r in results if r["status"] == "pass")
    warn_count = sum(1 for r in results if r["status"] == "warn")
    fail_count = sum(1 for r in results if r["status"] == "fail")

    summary = {
        "total": len(results),
        "pass": pass_count,
        "warn": warn_count,
        "fail": fail_count,
        "checked_at": now.isoformat(),
    }
    logger.info(f"Verification complete: {summary}")
    return summary


def get_verification_status():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM verification_results ORDER BY deviation DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not rows:
        return {"last_checked": None, "total": 0, "pass": 0, "warn": 0, "fail": 0, "heroes": []}

    checked_at = rows[0]["checked_at"] if rows else None
    pass_count = sum(1 for r in rows if r["status"] == "pass")
    warn_count = sum(1 for r in rows if r["status"] == "warn")
    fail_count = sum(1 for r in rows if r["status"] == "fail")

    return {
        "last_checked": checked_at,
        "total": len(rows),
        "pass": pass_count,
        "warn": warn_count,
        "fail": fail_count,
        "heroes": [
            {
                "hero_id": r["entity_id"],
                "hero_name": r["entity_name"],
                "expected_value": r["expected_value"],
                "actual_value": r["actual_value"],
                "deviation": r["deviation"],
                "status": r["status"],
                "sample_size": r["sample_size"],
            }
            for r in rows
        ],
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_hero_verification()
    print(json.dumps(result, indent=2))

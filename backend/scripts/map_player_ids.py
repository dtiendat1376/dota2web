"""
Player ID mapper: maps internal player names to Steam32 account IDs.

Uses OpenDota /api/search?q={name} to find Steam32 IDs.
Disambiguates using team context from our database.

Priority tiers:
  T1: Players from top 20 teams (highest value)
  T2: Top 50 most-appearance players
  T3: All players in recent matches (2024+)
  T4: All remaining players

Run: python -m backend.scripts.map_player_ids
"""

import json
import os
import time
import logging
import sqlite3
from datetime import datetime, timezone

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

import requests

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "dota2.db")
QUOTA_FILE = os.path.join(DATA_DIR, "api_quota.json")
MAPPER_PROGRESS = os.path.join(DATA_DIR, "mapper_progress.json")
ERROR_LOG = os.path.join(DATA_DIR, "fetch_errors.log")

OPENDOTA_BASE = "https://api.opendota.com/api"
SLEEP_BETWEEN = 1.11
DAILY_LIMIT = 2950
MAPPER_QUOTA = DAILY_LIMIT * 1 // 5  # 590 calls/day (20%)

logger = logging.getLogger("map_player_ids")


def _get_quota():
    if os.path.exists(QUOTA_FILE):
        with open(QUOTA_FILE, "r") as f:
            if _HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                if _HAS_FCNTL:
                    fcntl.flock(f, fcntl.LOCK_UN)
    return {"date": None, "fetcher_calls": 0, "mapper_calls": 0, "daily_limit": 2950}


def _save_quota(quota):
    with open(QUOTA_FILE, "w") as f:
        if _HAS_FCNTL:
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(quota, f, indent=2)
        finally:
            if _HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_UN)


def _get_progress():
    if os.path.exists(MAPPER_PROGRESS):
        with open(MAPPER_PROGRESS, "r") as f:
            return json.load(f)
    return {
        "mapped_today": 0,
        "mapped_total": 0,
        "failed": 0,
        "skipped": 0,
        "last_player": None,
        "last_date": None,
        "is_running": False,
        "started_at": None,
        "last_search_at": None,
    }


def _save_progress(state):
    with open(MAPPER_PROGRESS, "w") as f:
        json.dump(state, f, indent=2)


def _get_top_teams(limit=20):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT team_name, COUNT(*) as cnt
        FROM (
            SELECT team1 as team_name FROM matches
            UNION ALL
            SELECT team2 as team_name FROM matches
        )
        GROUP BY team_name
        ORDER BY cnt DESC
        LIMIT ?
    """, (limit,))
    teams = [row[0] for row in cur.fetchall()]
    conn.close()
    return teams


def _get_team_players(team_name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    player_ids = set()
    for col in ["player1_1","player1_2","player1_3","player1_4","player1_5",
                 "player2_1","player2_2","player2_3","player2_4","player2_5"]:
        cur.execute(f"SELECT DISTINCT {col} FROM matches WHERE {col} IS NOT NULL AND (team1=? OR team2=?)", (team_name, team_name))
        for row in cur.fetchall():
            player_ids.add(row[0])
    players = []
    for pid in player_ids:
        cur.execute("SELECT player_name FROM players WHERE player_id=?", (pid,))
        row = cur.fetchone()
        if row:
            players.append((pid, row[0]))
    conn.close()
    return players


def _get_top_players(limit=50):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    counts = {}
    for col in ["player1_1","player1_2","player1_3","player1_4","player1_5",
                 "player2_1","player2_2","player2_3","player2_4","player2_5"]:
        cur.execute(f"SELECT {col}, COUNT(*) FROM matches WHERE {col} IS NOT NULL GROUP BY {col}")
        for pid, cnt in cur.fetchall():
            counts[pid] = counts.get(pid, 0) + cnt
    top_ids = sorted(counts.keys(), key=lambda x: counts[x], reverse=True)[:limit]
    players = []
    for pid in top_ids:
        cur.execute("SELECT player_name FROM players WHERE player_id=?", (pid,))
        row = cur.fetchone()
        if row:
            players.append((pid, row[0]))
    conn.close()
    return players


def _get_recent_players(year=2024):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    player_ids = set()
    for col in ["player1_1","player1_2","player1_3","player1_4","player1_5",
                 "player2_1","player2_2","player2_3","player2_4","player2_5"]:
        cur.execute(f"SELECT DISTINCT {col} FROM matches WHERE {col} IS NOT NULL AND match_datetime >= ?", (f"{year}-01-01",))
        for row in cur.fetchall():
            if row[0]:
                player_ids.add(row[0])
    players = []
    for pid in player_ids:
        cur.execute("SELECT player_name FROM players WHERE player_id=?", (pid,))
        row = cur.fetchone()
        if row:
            players.append((pid, row[0]))
    conn.close()
    return players


def _get_unmapped_players():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT p.player_id, p.player_name
        FROM players p
        WHERE NOT EXISTS (
            SELECT 1 FROM player_id_map m WHERE m.player_name = p.player_name
        )
        ORDER BY p.player_name
    """)
    players = cur.fetchall()
    conn.close()
    return players


def _get_player_teams(player_name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    teams = set()
    cur.execute("""
        SELECT DISTINCT team1 FROM matches WHERE player1_1 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player1_2 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player1_3 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player1_4 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player1_5 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player2_1 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player2_2 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player2_3 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player2_4 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player2_5 IN (SELECT player_id FROM players WHERE player_name=?)
    """, (player_name,)*10)
    for row in cur.fetchall():
        teams.add(row[0])
    cur.execute("""
        SELECT DISTINCT team2 FROM matches WHERE player1_1 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player1_2 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player1_3 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player1_4 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player1_5 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player2_1 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player2_2 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player2_3 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player2_4 IN (SELECT player_id FROM players WHERE player_name=?)
        OR player2_5 IN (SELECT player_id FROM players WHERE player_name=?)
    """, (player_name,)*10)
    for row in cur.fetchall():
        teams.add(row[0])
    conn.close()
    return teams


def search_player(session, player_name):
    try:
        resp = session.get(f"{OPENDOTA_BASE}/search", params={"q": player_name}, timeout=30)
        if resp.status_code == 429:
            logger.warning("Rate limited. Sleeping 60s.")
            time.sleep(60)
            resp = session.get(f"{OPENDOTA_BASE}/search", params={"q": player_name}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Search failed for '{player_name}': {e}")
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} search player={player_name} error={e}\n")
        return None


def disambiguate(results, player_name):
    if not results:
        return None, 0.0
    if len(results) == 1:
        return results[0]["account_id"], 1.0
    for r in results:
        steam_name = r.get("personaname", "")
        if steam_name.lower() == player_name.lower():
            return r["account_id"], 0.9
    return results[0]["account_id"], 0.3


def store_mapping(player_name, team_name, steam32_id, confidence):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute("""
        INSERT OR REPLACE INTO player_id_map (player_name, team_name, steam32_id, confidence, searched_at)
        VALUES (?, ?, ?, ?, ?)
    """, (player_name, team_name, steam32_id, confidence, now))
    conn.commit()
    conn.close()


def get_mapper_status():
    state = _get_progress()
    quota = _get_quota()
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM player_id_map WHERE steam32_id IS NOT NULL")
        mapped = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM player_id_map WHERE steam32_id IS NULL")
        uncertain = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM players")
        total = cur.fetchone()[0]
        conn.close()
    except Exception:
        mapped = uncertain = total = 0

    return {
        "mapped": mapped,
        "uncertain": uncertain,
        "total_players": total,
        "mapped_today": state.get("mapped_today", 0),
        "mapper_calls_today": quota.get("mapper_calls", 0),
        "mapper_quota": MAPPER_QUOTA,
        "is_running": state.get("is_running", False),
        "last_search_at": state.get("last_search_at"),
    }


def map_batch(players, quota, max_calls=None):
    state = _get_progress()
    today = datetime.now(timezone.utc).date().isoformat()
    if state.get("last_date") != today:
        state["mapped_today"] = 0
        state["last_date"] = today

    state["is_running"] = True
    state["started_at"] = state.get("started_at") or datetime.now(timezone.utc).isoformat()
    _save_progress(state)

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    calls_made = 0

    for player_id, player_name in players:
        if max_calls and calls_made >= max_calls:
            logger.info(f"Mapper batch limit reached ({calls_made}/{max_calls}). Stopping.")
            break

        db_teams = _get_player_teams(player_name)
        if not db_teams:
            db_teams = {"Unknown"}

        for team_name in db_teams:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT steam32_id FROM player_id_map WHERE player_name=? AND team_name=?", (player_name, team_name))
            existing = cur.fetchone()
            conn.close()
            if existing and existing[0]:
                state["skipped"] += 1
                continue

            results = search_player(session, player_name)
            calls_made += 1
            quota["mapper_calls"] += 1
            _save_quota(quota)

            if results is None:
                state["failed"] += 1
                state["last_player"] = player_name
                state["last_search_at"] = datetime.now(timezone.utc).isoformat()
                _save_progress(state)
                time.sleep(SLEEP_BETWEEN)
                continue

            steam32_id, confidence = disambiguate(results, player_name)
            store_mapping(player_name, team_name, steam32_id, confidence)

            state["mapped_today"] += 1
            state["mapped_total"] += 1
            state["last_player"] = player_name
            state["last_search_at"] = datetime.now(timezone.utc).isoformat()
            _save_progress(state)

            if state["mapped_today"] % 50 == 0:
                logger.info(f"Mapper progress: {state['mapped_today']} mapped, {quota['mapper_calls']}/{MAPPER_QUOTA} quota used")

            time.sleep(SLEEP_BETWEEN)

    state["is_running"] = False
    state["started_at"] = None
    _save_progress(state)
    logger.info(f"Mapper batch complete. Mapped: {state['mapped_total']}, Failed: {state['failed']}, Skipped: {state['skipped']}")
    return calls_made


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    quota = _get_quota()
    today = datetime.now(timezone.utc).date().isoformat()
    if quota.get("date") != today:
        quota["date"] = today
        quota["fetcher_calls"] = 0
        quota["mapper_calls"] = 0
        _save_quota(quota)

    remaining = max(0, MAPPER_QUOTA - quota["mapper_calls"])
    if remaining <= 0:
        print(f"Mapper quota exhausted ({quota['mapper_calls']}/{MAPPER_QUOTA}). Try again tomorrow.")
        exit(0)

    print(f"Mapper quota remaining: {remaining}/{MAPPER_QUOTA}")
    print("Priority T1: Top 20 teams...")
    top_teams = _get_top_teams(20)
    t1_players = []
    for team in top_teams:
        t1_players.extend(_get_team_players(team))
    t1_players = list(set(t1_players))
    print(f"  Found {len(t1_players)} unique players from top 20 teams")

    calls = map_batch(t1_players, quota, max_calls=remaining)
    print(f"T1 complete. Used {calls} API calls.")

    remaining = max(0, MAPPER_QUOTA - quota["mapper_calls"])
    if remaining > 0:
        print(f"\nPriority T2: Top 50 most-appearance players...")
        t2_players = _get_top_players(50)
        calls = map_batch(t2_players, quota, max_calls=remaining)
        print(f"T2 complete. Used {calls} API calls.")

    remaining = max(0, MAPPER_QUOTA - quota["mapper_calls"])
    if remaining > 0:
        print(f"\nPriority T3: Recent players (2024+)...")
        t3_players = _get_recent_players(2024)
        print(f"  Found {len(t3_players)} recent players")
        calls = map_batch(t3_players, quota, max_calls=remaining)
        print(f"T3 complete. Used {calls} API calls.")

    print(f"\nTotal mapped today: {_get_progress()['mapped_today']}")
    print(f"Quota used: {quota['mapper_calls']}/{MAPPER_QUOTA}")

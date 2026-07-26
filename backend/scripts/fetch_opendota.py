"""
OpenDota match detail fetcher + player ID mapper (interleaved).

Runs as a daemon thread started from FastAPI startup.
Fetches /api/matches/{dota_game_id} and maps player names to Steam32 IDs.

Rate limits: 2,950 calls/day shared 50/50 between fetcher and mapper.
Progress: tracked in data/opendota_progress.json + data/mapper_progress.json
"""

import json
import os
import time
import logging
from datetime import datetime, date, timezone
from threading import Event

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

import requests
import sqlite3

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "dota2.db")
HEROES_CACHE = os.path.join(DATA_DIR, "heroes.json")
PROGRESS_FILE = os.path.join(DATA_DIR, "opendota_progress.json")
QUOTA_FILE = os.path.join(DATA_DIR, "api_quota.json")
ERROR_LOG = os.path.join(DATA_DIR, "fetch_errors.log")

OPENDOTA_BASE = "https://api.opendota.com/api"
DAILY_LIMIT = 2950
FETCHER_QUOTA = DAILY_LIMIT * 4 // 5  # 2360 calls/day for matches (80%)
MAPPER_QUOTA = DAILY_LIMIT - FETCHER_QUOTA  # 590 calls/day for player mapping (20%)
SLEEP_BETWEEN = 1.11  # seconds (~54 req/min)

logger = logging.getLogger("fetch_opendota")


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
    return {
        "date": None,
        "fetcher_calls": 0,
        "mapper_calls": 0,
        "daily_limit": DAILY_LIMIT,
    }


def _save_quota(quota):
    with open(QUOTA_FILE, "w") as f:
        if _HAS_FCNTL:
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(quota, f, indent=2)
        finally:
            if _HAS_FCNTL:
                fcntl.flock(f, fcntl.LOCK_UN)


def _reset_quota_if_new_day(quota):
    today = date.today().isoformat()
    if quota.get("date") != today:
        quota["date"] = today
        quota["fetcher_calls"] = 0
        quota["mapper_calls"] = 0
        _save_quota(quota)
        logger.info(f"New day ({today}), quota reset.")
    return quota


def _fetcher_quota_remaining(quota):
    return max(0, FETCHER_QUOTA - quota["fetcher_calls"])


def _mapper_quota_remaining(quota):
    return max(0, MAPPER_QUOTA - quota["mapper_calls"])


def _get_unmapped_batch(limit):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT p.player_id, p.player_name
        FROM players p
        WHERE NOT EXISTS (
            SELECT 1 FROM player_id_map m WHERE m.player_name = p.player_name
        )
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))
    players = cur.fetchall()
    conn.close()
    return players


def _get_player_teams(player_name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    teams = set()
    for col in ["team1", "team2"]:
        cur.execute(f"""
            SELECT DISTINCT {col} FROM matches
            WHERE {col} IS NOT NULL AND (
                player1_1 IN (SELECT player_id FROM players WHERE player_name=?)
                OR player1_2 IN (SELECT player_id FROM players WHERE player_name=?)
                OR player1_3 IN (SELECT player_id FROM players WHERE player_name=?)
                OR player1_4 IN (SELECT player_id FROM players WHERE player_name=?)
                OR player1_5 IN (SELECT player_id FROM players WHERE player_name=?)
                OR player2_1 IN (SELECT player_id FROM players WHERE player_name=?)
                OR player2_2 IN (SELECT player_id FROM players WHERE player_name=?)
                OR player2_3 IN (SELECT player_id FROM players WHERE player_name=?)
                OR player2_4 IN (SELECT player_id FROM players WHERE player_name=?)
                OR player2_5 IN (SELECT player_id FROM players WHERE player_name=?)
            )
        """, (player_name,)*10)
        for row in cur.fetchall():
            teams.add(row[0])
    conn.close()
    return teams if teams else {"Unknown"}


def _disambiguate(results, player_name):
    if not results:
        return None, 0.0
    if len(results) == 1:
        return results[0]["account_id"], 1.0
    for r in results:
        steam_name = r.get("personaname", "")
        if steam_name.lower() == player_name.lower():
            return r["account_id"], 0.9
    return results[0]["account_id"], 0.3


def _store_mapping(player_name, team_name, steam32_id, confidence):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute("""
        INSERT OR REPLACE INTO player_id_map (player_name, team_name, steam32_id, confidence, searched_at)
        VALUES (?, ?, ?, ?, ?)
    """, (player_name, team_name, steam32_id, confidence, now))
    conn.commit()
    conn.close()


def _run_mapper_batch(session, quota, batch_size):
    players = _get_unmapped_batch(batch_size)
    if not players:
        return

    logger.info(f"Mapper: mapping {len(players)} players...")
    for player_id, player_name in players:
        if _mapper_quota_remaining(quota) <= 0:
            break
        teams = _get_player_teams(player_name)
        for team_name in teams:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT steam32_id FROM player_id_map WHERE player_name=? AND team_name=?", (player_name, team_name))
            existing = cur.fetchone()
            conn.close()
            if existing and existing[0]:
                continue
            try:
                resp = session.get(f"{OPENDOTA_BASE}/search", params={"q": player_name}, timeout=30)
                if resp.status_code == 429:
                    time.sleep(60)
                    resp = session.get(f"{OPENDOTA_BASE}/search", params={"q": player_name}, timeout=30)
                quota["mapper_calls"] += 1
                _save_quota(quota)
                if resp.status_code != 200:
                    logger.error(f"Search failed for '{player_name}': HTTP {resp.status_code}")
                    time.sleep(SLEEP_BETWEEN)
                    continue
                results = resp.json()
                steam32_id, confidence = _disambiguate(results, player_name)
                _store_mapping(player_name, team_name, steam32_id, confidence)
                time.sleep(SLEEP_BETWEEN)
            except requests.exceptions.RequestException as e:
                logger.error(f"Mapper error for '{player_name}': {e}")
                with open(ERROR_LOG, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now(timezone.utc).isoformat()} map player={player_name} error={e}\n")
                time.sleep(5)


def _get_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {
        "fetched_today": 0,
        "fetched_total": 0,
        "failed": 0,
        "not_found": 0,
        "last_game_id": None,
        "last_date": None,
        "is_running": False,
        "started_at": None,
        "last_fetch_at": None,
    }


def _save_progress(state):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _fetch_heroes():
    if os.path.exists(HEROES_CACHE):
        with open(HEROES_CACHE, "r") as f:
            return json.load(f)
    try:
        resp = requests.get(f"{OPENDOTA_BASE}/heroes", timeout=30)
        resp.raise_for_status()
        heroes = resp.json()
        with open(HEROES_CACHE, "w") as f:
            json.dump(heroes, f, indent=2)
        logger.info(f"Cached {len(heroes)} heroes")
        return heroes
    except Exception as e:
        logger.error(f"Failed to fetch heroes: {e}")
        return []


def _load_heroes_to_db(heroes):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for h in heroes:
        cur.execute(
            """INSERT OR IGNORE INTO heroes (hero_id, name, localized_name, primary_attr, attack_type, roles)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (h["id"], h["name"], h["localized_name"], h.get("primary_attr"),
             h.get("attack_type"), json.dumps(h.get("roles", [])))
        )
    conn.commit()
    conn.close()


def _get_pending_game_ids():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT dota_game_id FROM matches WHERE dota_game_id IS NOT NULL "
        "AND dota_game_id NOT IN (SELECT dota_game_id FROM match_details) "
        "ORDER BY dota_game_id"
    )
    ids = [row[0] for row in cur.fetchall()]
    conn.close()
    return ids


def _store_match(data):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    game_id = data["match_id"]

    cur.execute(
        """INSERT OR REPLACE INTO match_details
           (dota_game_id, duration, radiant_win, radiant_score, dire_score,
            game_mode, lobby_type, patch, region, start_time, picks_bans, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (game_id, data.get("duration"), data.get("radiant_win"),
         data.get("radiant_score"), data.get("dire_score"),
         data.get("game_mode"), data.get("lobby_type"),
         data.get("patch"), data.get("region"), data.get("start_time"),
         json.dumps(data.get("picks_bans")) if data.get("picks_bans") else None,
         now)
    )

    cur.execute("DELETE FROM match_player_stats WHERE dota_game_id = ?", (game_id,))

    for p in data.get("players", []):
        cur.execute(
            """INSERT INTO match_player_stats
               (dota_game_id, player_slot, hero_id, kills, deaths, assists,
                gold_per_min, xp_per_min, last_hits, denies, hero_damage,
                tower_damage, hero_healing, net_worth, level, win)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (game_id, p.get("player_slot"), p.get("hero_id"),
             p.get("kills"), p.get("deaths"), p.get("assists"),
             p.get("gold_per_min"), p.get("xp_per_min"),
             p.get("last_hits"), p.get("denies"),
             p.get("hero_damage"), p.get("tower_damage"),
             p.get("hero_healing"), p.get("net_worth"),
             p.get("level"), p.get("win"))
        )

    cur.execute(
        "UPDATE matches SET has_game_data = 1 WHERE dota_game_id = ?",
        (game_id,)
    )
    conn.commit()
    conn.close()


def _run_initial_discovery():
    try:
        from backend.scripts.bulk_discovery import run_discovery, get_status
        disc_status = get_status()
        if disc_status.get("pro_players_in_db", 0) == 0:
            logger.info("No discovery data found. Running initial bulk discovery...")
            run_discovery(phases=[1])
        else:
            logger.info(f"Discovery data exists: {disc_status.get('pro_players_in_db', 0)} pro players, "
                        f"{disc_status.get('teams_in_db', 0)} teams.")
    except Exception as e:
        logger.error(f"Initial discovery failed: {e}")


def fetch_loop(stop_event=None):
    if stop_event is None:
        stop_event = Event()

    _run_initial_discovery()

    state = _get_progress()
    quota = _get_quota()
    quota = _reset_quota_if_new_day(quota)

    today = date.today().isoformat()
    if state.get("last_date") != today:
        state["fetched_today"] = 0
        state["last_date"] = today

    remaining = _fetcher_quota_remaining(quota)
    mapper_remaining = _mapper_quota_remaining(quota)
    if remaining <= 0 and mapper_remaining <= 0:
        logger.info(f"All quota exhausted (fetcher: {quota['fetcher_calls']}/{FETCHER_QUOTA}, mapper: {quota['mapper_calls']}/{MAPPER_QUOTA}). Stopping.")
        state["is_running"] = False
        _save_progress(state)
        return

    heroes = _fetch_heroes()
    _load_heroes_to_db(heroes)

    try:
        from backend.scripts.verify_hero_stats import run_hero_verification
        verification = run_hero_verification()
        logger.info(f"Verification: {verification}")
    except Exception as e:
        logger.error(f"Verification failed: {e}")

    pending = _get_pending_game_ids()
    logger.info(f"Pending games: {len(pending)}, fetcher quota: {remaining}/{FETCHER_QUOTA}, mapper quota: {mapper_remaining}/{MAPPER_QUOTA}")

    state["is_running"] = True
    state["started_at"] = state.get("started_at") or datetime.now(timezone.utc).isoformat()
    _save_progress(state)

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    BATCH_SIZE = 25
    game_idx = 0

    while game_idx < len(pending):
        if stop_event.is_set():
            logger.info("Stop event received. Pausing.")
            state["is_running"] = False
            _save_progress(state)
            return

        remaining = _fetcher_quota_remaining(quota)
        mapper_remaining = _mapper_quota_remaining(quota)
        if remaining <= 0 and mapper_remaining <= 0:
            logger.info(f"All quota exhausted. Stopping.")
            state["is_running"] = False
            _save_progress(state)
            return

        if remaining > 0:
            batch_end = min(game_idx + BATCH_SIZE, len(pending))
            for i in range(game_idx, batch_end):
                if stop_event.is_set():
                    state["is_running"] = False
                    _save_progress(state)
                    return
                if _fetcher_quota_remaining(quota) <= 0:
                    break
                game_id = pending[i]
                try:
                    resp = session.get(f"{OPENDOTA_BASE}/matches/{game_id}", timeout=30)
                    if resp.status_code == 429:
                        logger.warning("Rate limited. Sleeping 60s.")
                        time.sleep(60)
                        resp = session.get(f"{OPENDOTA_BASE}/matches/{game_id}", timeout=30)
                    quota["fetcher_calls"] += 1
                    _save_quota(quota)
                    if resp.status_code == 404:
                        state["not_found"] += 1
                        state["last_game_id"] = game_id
                        state["fetched_today"] += 1
                        state["fetched_total"] += 1
                        state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
                        _save_progress(state)
                        time.sleep(SLEEP_BETWEEN)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    if not data.get("players"):
                        state["not_found"] += 1
                        state["last_game_id"] = game_id
                        state["fetched_today"] += 1
                        state["fetched_total"] += 1
                        state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
                        _save_progress(state)
                        time.sleep(SLEEP_BETWEEN)
                        continue
                    _store_match(data)
                    state["fetched_today"] += 1
                    state["fetched_total"] += 1
                    state["last_game_id"] = game_id
                    state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
                    _save_progress(state)
                    if state["fetched_today"] % 100 == 0:
                        logger.info(f"Fetch progress: {state['fetched_today']} fetched, {quota['fetcher_calls']}/{FETCHER_QUOTA} quota")
                    time.sleep(SLEEP_BETWEEN)
                except requests.exceptions.RequestException as e:
                    state["failed"] += 1
                    state["last_game_id"] = game_id
                    state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
                    _save_progress(state)
                    with open(ERROR_LOG, "a", encoding="utf-8") as f:
                        f.write(f"{datetime.now(timezone.utc).isoformat()} game_id={game_id} error={e}\n")
                    logger.error(f"Error fetching {game_id}: {e}")
                    time.sleep(5)
            game_idx = batch_end

        if _mapper_quota_remaining(quota) > 0:
            _run_mapper_batch(session, quota, BATCH_SIZE)

    state["is_running"] = False
    state["started_at"] = None
    _save_progress(state)
    logger.info(f"Fetch complete. Total: {state['fetched_total']}, Failed: {state['failed']}, 404: {state['not_found']}")


def get_status():
    state = _get_progress()
    quota = _get_quota()
    quota = _reset_quota_if_new_day(quota)
    pending_count = 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM matches WHERE dota_game_id IS NOT NULL "
            "AND dota_game_id NOT IN (SELECT dota_game_id FROM match_details)"
        )
        pending_count = cur.fetchone()[0]
        conn.close()
    except Exception:
        pass

    return {
        "fetched_today": state.get("fetched_today", 0),
        "fetcher_quota": FETCHER_QUOTA,
        "mapper_quota": MAPPER_QUOTA,
        "fetcher_calls_today": quota["fetcher_calls"],
        "mapper_calls_today": quota["mapper_calls"],
        "daily_limit": DAILY_LIMIT,
        "fetched_total": state.get("fetched_total", 0),
        "failed": state.get("failed", 0),
        "not_found": state.get("not_found", 0),
        "pending": pending_count,
        "is_running": state.get("is_running", False),
        "last_fetch_at": state.get("last_fetch_at"),
        "last_game_id": state.get("last_game_id"),
    }


stop_event = Event()


def start_fetcher():
    logger.info("Starting OpenDota fetcher daemon...")
    while not stop_event.is_set():
        fetch_loop(stop_event)
        if not stop_event.is_set():
            stop_event.wait(300)


def stop_fetcher():
    stop_event.set()

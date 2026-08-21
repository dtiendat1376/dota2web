"""
OpenDota match detail fetcher + player ID mapper (interleaved).

Runs as a daemon thread started from FastAPI startup.
Fetches /api/matches/{dota_game_id} and maps player names to Steam32 IDs.

Rate limits: 2,950 calls/day shared between buckets; the fetcher gets the
largest slice (match details are the priority), the mapper a small cap, and
live/utility calls a hard cap. Failed matches are retried up to a bounded
number of times and then marked permanently to stop wasting quota.
Progress: tracked in data/opendota_progress.json + data/mapper_progress.json

All HTTP + quota handling is delegated to backend.app.services.opendota_client.
"""

import json
import os
import logging
import concurrent.futures
from datetime import datetime, date, timezone
from threading import Event

import sqlite3

from backend.app.services.opendota_client import (
    api_get,
    quota_remaining,
    get_quota,
    DAILY_LIMIT,
    FETCHER_QUOTA,
    MAPPER_QUOTA,
)
from backend.app.services.pro_player_mapper import (
    try_local_mapping,
    mine_match_payload,
)

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "dota2.db")
HEROES_CACHE = os.path.join(DATA_DIR, "heroes.json")
PROGRESS_FILE = os.path.join(DATA_DIR, "opendota_progress.json")
ERROR_LOG = os.path.join(DATA_DIR, "fetch_errors.log")
ATTEMPTS_FILE = os.path.join(DATA_DIR, "fetch_attempts.json")

FETCH_WORKERS = int(os.getenv("OPENDOTA_FETCH_WORKERS", "3"))
MAX_FETCH_RETRIES = int(os.getenv("OPENDOTA_MAX_RETRIES", "2"))

logger = logging.getLogger("fetch_opendota")


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


def _run_mapper_batch(batch_size):
    players = _get_unmapped_batch(batch_size)
    if not players:
        return

    logger.info(f"Mapper: mapping {len(players)} players...")
    for player_id, player_name in players:
        teams = _get_player_teams(player_name)
        conn = sqlite3.connect(DB_PATH)
        local_id = try_local_mapping(conn, player_name, teams)
        conn.commit()
        conn.close()
        if local_id is not None:
            logger.info(f"Mapper: mapped '{player_name}' locally (pro_player_index, {local_id})")
            continue
        if quota_remaining("mapper") <= 0:
            break
        unmapped = []
        for team_name in teams:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT steam32_id FROM player_id_map WHERE player_name=? AND team_name=?", (player_name, team_name))
            existing = cur.fetchone()
            conn.close()
            if existing and existing[0]:
                continue
            unmapped.append(team_name)
        if not unmapped:
            continue
        resp = api_get("/search", params={"q": player_name}, bucket="mapper")
        if resp is None:
            logger.warning(f"Mapper: no response for '{player_name}'. Stopping batch.")
            return
        if resp.status_code != 200:
            logger.error(f"Search failed for '{player_name}': HTTP {resp.status_code}")
            continue
        results = resp.json()
        steam32_id, confidence = _disambiguate(results, player_name)
        for team_name in unmapped:
            _store_mapping(player_name, team_name, steam32_id, confidence)


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


# ─── Failure retry tracking ────────────────────────────────────────────
# Some game IDs fail permanently (dead IDs -> 521/522 or read timeouts).
# Without a cap the daily reset would re-fetch them forever. We track the
# number of failed attempts per game_id and stop retrying past the cap.


def _load_attempts():
    if os.path.exists(ATTEMPTS_FILE):
        try:
            with open(ATTEMPTS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_attempts(attempts):
    with open(ATTEMPTS_FILE, "w") as f:
        json.dump(attempts, f)


def _bump_attempt(game_id):
    attempts = _load_attempts()
    attempts[str(game_id)] = attempts.get(str(game_id), 0) + 1
    _save_attempts(attempts)


def _clear_attempt(game_id):
    attempts = _load_attempts()
    if str(game_id) in attempts:
        del attempts[str(game_id)]
        _save_attempts(attempts)


def _is_dead(game_id):
    attempts = _load_attempts()
    return attempts.get(str(game_id), 0) >= MAX_FETCH_RETRIES


def _fetch_heroes():
    if os.path.exists(HEROES_CACHE):
        with open(HEROES_CACHE, "r") as f:
            return json.load(f)
    try:
        resp = api_get("/heroes", bucket="other")
        if resp is None:
            return []
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
    try:
        cur.execute(
            "SELECT DISTINCT dota_game_id FROM matches WHERE dota_game_id IS NOT NULL "
            "AND fetch_status = 'pending' "
            "ORDER BY dota_game_id DESC"
        )
    except sqlite3.OperationalError:
        # Fallback for databases that have not been migrated (no fetch_status column)
        cur.execute(
            "SELECT DISTINCT dota_game_id FROM matches WHERE dota_game_id IS NOT NULL "
            "AND dota_game_id NOT IN (SELECT dota_game_id FROM match_details) "
            "ORDER BY dota_game_id DESC"
        )
    ids = [row[0] for row in cur.fetchall()]
    conn.close()
    return ids


def _mark_fetch_status(game_id, status):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "UPDATE matches SET fetch_status = ? WHERE dota_game_id = ?",
            (status, game_id),
        )
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass


def _retry_failed_matches():
    """Reset transient failures to pending, retire permanent ones.

    Runs once per day. Matches that failed fewer times than the retry cap go
    back to 'pending' for another attempt; matches past the cap are marked
    'not_found' permanently so the daily reset stops wasting quota on them.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT dota_game_id FROM matches WHERE fetch_status = 'failed'")
        failed_ids = [row[0] for row in cur.fetchall()]
        for game_id in failed_ids:
            if _is_dead(game_id):
                cur.execute(
                    "UPDATE matches SET fetch_status = 'not_found' WHERE dota_game_id = ?",
                    (game_id,),
                )
                _clear_attempt(game_id)
            else:
                cur.execute(
                    "UPDATE matches SET fetch_status = 'pending' WHERE dota_game_id = ?",
                    (game_id,),
                )
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass


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

    try:
        cur.execute(
            "UPDATE matches SET has_game_data = 1, fetch_status = 'fetched' WHERE dota_game_id = ?",
            (game_id,)
        )
    except sqlite3.OperationalError:
        cur.execute(
            "UPDATE matches SET has_game_data = 1 WHERE dota_game_id = ?",
            (game_id,)
        )

    team_row = cur.execute(
        "SELECT team1, team2 FROM matches WHERE dota_game_id = ?", (game_id,)
    ).fetchone()
    if team_row:
        mine_match_payload(cur, team_row[0], team_row[1], data.get("players", []))

    conn.commit()
    conn.close()


def _handle_match_response(game_id, resp, state):
    """Persist the result of one match fetch and update progress.

    Runs on the caller (main) thread as worker futures complete, so all DB
    and file writes stay single-threaded.
    """
    if resp is None:
        _mark_fetch_status(game_id, "failed")
        _bump_attempt(game_id)
        state["failed"] += 1
        state["last_game_id"] = game_id
        state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
        _save_progress(state)
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} game_id={game_id} error=fetch failed\n")
        return
    if resp.status_code == 404:
        _mark_fetch_status(game_id, "not_found")
        _clear_attempt(game_id)
        state["not_found"] += 1
        state["last_game_id"] = game_id
        state["fetched_today"] += 1
        state["fetched_total"] += 1
        state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
        _save_progress(state)
        return
    try:
        data = resp.json()
    except ValueError:
        _mark_fetch_status(game_id, "failed")
        _bump_attempt(game_id)
        state["failed"] += 1
        state["last_game_id"] = game_id
        state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
        _save_progress(state)
        return
    if not data.get("players"):
        _mark_fetch_status(game_id, "not_found")
        _clear_attempt(game_id)
        state["not_found"] += 1
        state["last_game_id"] = game_id
        state["fetched_today"] += 1
        state["fetched_total"] += 1
        state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
        _save_progress(state)
        return
    _store_match(data)
    _clear_attempt(game_id)
    state["fetched_today"] += 1
    state["fetched_total"] += 1
    state["last_game_id"] = game_id
    state["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
    _save_progress(state)
    if state["fetched_today"] % 100 == 0:
        fetcher_used = FETCHER_QUOTA - quota_remaining("fetcher")
        logger.info(f"Fetch progress: {state['fetched_today']} fetched, {fetcher_used}/{FETCHER_QUOTA} quota")


def _fetch_batch(game_ids, stop_event, state):
    """Fetch a batch of match details concurrently.

    HTTP calls run on a small thread pool; the shared rate limiter in
    opendota_client keeps total throughput under the per-minute cap. DB
    writes and progress updates happen in the caller thread via
    _handle_match_response.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=FETCH_WORKERS) as executor:
        futures = {
            executor.submit(api_get, f"/matches/{game_id}", bucket="fetcher"): game_id
            for game_id in game_ids
        }
        for future in concurrent.futures.as_completed(futures):
            if stop_event.is_set():
                for f in futures:
                    f.cancel()
                break
            game_id = futures[future]
            try:
                resp = future.result()
            except Exception as e:
                logger.error(f"Unexpected error fetching {game_id}: {e}")
                resp = None
            _handle_match_response(game_id, resp, state)


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
    quota = get_quota()

    today = date.today().isoformat()
    if state.get("last_date") != today:
        state["fetched_today"] = 0
        state["last_date"] = today
        _retry_failed_matches()

    remaining = quota_remaining("fetcher")
    mapper_remaining = quota_remaining("mapper")
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

    BATCH_SIZE = 25
    game_idx = 0

    while game_idx < len(pending):
        if stop_event.is_set():
            logger.info("Stop event received. Pausing.")
            state["is_running"] = False
            _save_progress(state)
            return

        remaining = quota_remaining("fetcher")
        mapper_remaining = quota_remaining("mapper")
        if remaining <= 0 and mapper_remaining <= 0:
            logger.info(f"All quota exhausted. Stopping.")
            state["is_running"] = False
            _save_progress(state)
            return

        if remaining > 0:
            batch_end = min(game_idx + BATCH_SIZE, len(pending))
            batch = [gid for gid in pending[game_idx:batch_end] if not _is_dead(gid)]
            batch = batch[:max(0, min(len(batch), quota_remaining("fetcher")))]
            if batch:
                _fetch_batch(batch, stop_event, state)
            game_idx = batch_end

        if quota_remaining("mapper") > 0:
            _run_mapper_batch(BATCH_SIZE)

    state["is_running"] = False
    state["started_at"] = None
    _save_progress(state)
    logger.info(f"Fetch complete. Total: {state['fetched_total']}, Failed: {state['failed']}, 404: {state['not_found']}")


def get_status():
    state = _get_progress()
    quota = get_quota()
    pending_count = 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM matches WHERE dota_game_id IS NOT NULL "
            "AND fetch_status = 'pending'"
        )
        pending_count = cur.fetchone()[0]
        conn.close()
    except Exception:
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
        "other_calls_today": quota.get("other_calls", 0),
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

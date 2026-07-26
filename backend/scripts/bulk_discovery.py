"""
Bulk OpenDota discovery: fetches pro matches, pro players, and teams.

Phase 1: Bulk discovery (~3 API calls)
  - /api/proMatches -> pro_match_index table (latest 100 only, no offset support)
  - /api/proPlayers -> pro_player_index table (all ~5000 pro players)
  - /api/teams -> team_open_data table (top 1000 teams)
  - Cross-reference pro matches to discover missing dota_game_ids
  - Bulk-map player IDs from pro player data

Phase 2: Team enrichment (~38 API calls for our teams)
  - /api/teams/{id}/matches -> team_open_matches table
  - /api/teams/{id}/players -> team_open_players table
  - Cross-reference team matches to discover missing dota_game_ids

NOTE: /api/proMatches does NOT support offset pagination.
      It always returns the latest 100 matches regardless of offset parameter.

Run as standalone script or imported by the fetcher daemon.
"""

import json
import os
import sqlite3
import time
import logging
from datetime import datetime, timezone

import requests

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "dota2.db")
TEAM_ALIASES_FILE = os.path.join(DATA_DIR, "team_aliases.json")
DISCOVERY_PROGRESS_FILE = os.path.join(DATA_DIR, "discovery_progress.json")

OPENDOTA_BASE = "https://api.opendota.com/api"
SLEEP_BETWEEN = 0.5

logger = logging.getLogger("bulk_discovery")


def _get_conn():
    return sqlite3.connect(DB_PATH)


def _load_team_aliases():
    if os.path.exists(TEAM_ALIASES_FILE):
        with open(TEAM_ALIASES_FILE, "r") as f:
            return json.load(f)
    return {}


def _load_progress():
    if os.path.exists(DISCOVERY_PROGRESS_FILE):
        with open(DISCOVERY_PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {
        "pro_matches_fetched": 0,
        "pro_players_fetched": 0,
        "teams_fetched": 0,
        "team_matches_fetched": 0,
        "team_players_fetched": 0,
        "dota_game_ids_discovered": 0,
        "player_ids_mapped": 0,
        "teams_enriched": 0,
        "last_run": None,
    }


def _save_progress(state):
    with open(DISCOVERY_PROGRESS_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _api_get(session, endpoint, params=None, retries=3):
    url = f"{OPENDOTA_BASE}{endpoint}"
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                wait = 60 if attempt < retries - 1 else 120
                logger.warning(f"Rate limited on {endpoint}. Sleeping {wait}s.")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                logger.warning(f"Retry {attempt+1} for {endpoint}: {e}")
                time.sleep(5)
            else:
                logger.error(f"Failed {endpoint} after {retries} attempts: {e}")
                return None
    return None


def _normalize_name(name):
    if not name:
        return ""
    return name.strip().lower().replace("  ", " ")


# ─── Phase 1a: Fetch pro matches (latest 100 only) ─────────────────────

def fetch_pro_matches(session, state):
    logger.info("Phase 1a: Fetching latest pro matches from OpenDota...")
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    cur = conn.cursor()

    data = _api_get(session, "/proMatches", params={"limit": 100})
    if not data:
        logger.error("Failed to fetch pro matches.")
        conn.close()
        return 0

    count = 0
    for m in data:
        try:
            cur.execute(
                """INSERT OR IGNORE INTO pro_match_index
                   (match_id, duration, start_time, radiant_team_id, radiant_name,
                    dire_team_id, dire_name, leagueid, league_name, series_id,
                    series_type, radiant_score, dire_score, radiant_win, version, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    m.get("match_id"), m.get("duration"), m.get("start_time"),
                    m.get("radiant_team_id"), m.get("radiant_name"),
                    m.get("dire_team_id"), m.get("dire_name"),
                    m.get("leagueid"), m.get("league_name"),
                    m.get("series_id"), m.get("series_type"),
                    m.get("radiant_score"), m.get("dire_score"),
                    1 if m.get("radiant_win") else 0,
                    m.get("version"), now,
                ),
            )
            count += 1
        except sqlite3.Error as e:
            logger.error(f"Error storing pro match {m.get('match_id')}: {e}")

    conn.commit()
    conn.close()
    state["pro_matches_fetched"] = count
    logger.info(f"Phase 1a complete: {count} pro matches stored.")
    return count


# ─── Phase 1b: Fetch pro players ────────────────────────────────────────

def fetch_pro_players(session, state):
    logger.info("Phase 1b: Fetching pro players from OpenDota...")
    now = datetime.now(timezone.utc).isoformat()
    data = _api_get(session, "/proPlayers")
    if not data:
        logger.error("Failed to fetch pro players.")
        return 0

    conn = _get_conn()
    cur = conn.cursor()
    count = 0
    for p in data:
        try:
            cur.execute(
                """INSERT OR REPLACE INTO pro_player_index
                   (account_id, name, country_code, fantasy_role, team_id,
                    team_name, team_tag, is_locked, is_pro, total_earnings,
                    last_match_time, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    p.get("account_id"), p.get("name"), p.get("country_code"),
                    p.get("fantasy_role"), p.get("team_id"),
                    p.get("team_name"), p.get("team_tag"),
                    1 if p.get("is_locked") else 0,
                    1 if p.get("is_pro") else 0,
                    p.get("total_earnings"), p.get("last_match_time"), now,
                ),
            )
            count += 1
        except sqlite3.Error as e:
            logger.error(f"Error storing pro player {p.get('account_id')}: {e}")

    conn.commit()
    conn.close()
    state["pro_players_fetched"] = count
    logger.info(f"Phase 1b complete: {count} pro players stored.")
    return count


# ─── Phase 1c: Fetch teams ──────────────────────────────────────────────

def fetch_teams(session, state):
    logger.info("Phase 1c: Fetching teams from OpenDota...")
    now = datetime.now(timezone.utc).isoformat()
    data = _api_get(session, "/teams")
    if not data:
        logger.error("Failed to fetch teams.")
        return 0

    conn = _get_conn()
    cur = conn.cursor()
    count = 0
    for t in data:
        try:
            cur.execute(
                """INSERT OR REPLACE INTO team_open_data
                   (team_id, name, tag, rating, wins, losses,
                    last_match_time, logo_url, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    t.get("team_id"), t.get("name"), t.get("tag"),
                    t.get("rating"), t.get("wins"), t.get("losses"),
                    t.get("last_match_time"), t.get("logo_url"), now,
                ),
            )
            count += 1
        except sqlite3.Error as e:
            logger.error(f"Error storing team {t.get('team_id')}: {e}")

    conn.commit()
    conn.close()
    state["teams_fetched"] = count
    logger.info(f"Phase 1c complete: {count} teams stored.")
    return count


# ─── Cross-reference: discover missing dota_game_ids ────────────────────

def discover_dota_game_ids(state):
    logger.info("Cross-referencing to discover missing dota_game_ids...")
    conn = _get_conn()
    cur = conn.cursor()
    count = 0

    # Pro matches: match_id from proMatches IS the dota_game_id
    cur.execute("""
        UPDATE matches SET dota_game_id = match_id
        WHERE dota_game_id IS NULL
        AND match_id IN (SELECT match_id FROM pro_match_index WHERE version IS NOT NULL)
    """)
    count += cur.rowcount

    # Team matches: match_id from team matches IS the dota_game_id
    cur.execute("""
        UPDATE matches SET dota_game_id = match_id
        WHERE dota_game_id IS NULL
        AND match_id IN (SELECT match_id FROM team_open_matches)
    """)
    count += cur.rowcount

    conn.commit()
    conn.close()
    state["dota_game_ids_discovered"] = count
    logger.info(f"Discovered {count} missing dota_game_ids.")
    return count


# ─── Bulk-map player IDs from pro player data ───────────────────────────

def bulk_map_player_ids(state):
    logger.info("Bulk-mapping player IDs from pro player data...")
    conn = _get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT p.player_id, p.player_name
        FROM players p
        WHERE NOT EXISTS (
            SELECT 1 FROM player_id_map m
            WHERE m.player_name = p.player_name AND m.steam32_id IS NOT NULL
        )
    """)
    unmapped = cur.fetchall()
    logger.info(f"Found {len(unmapped)} players without steam32_id mapping.")

    cur.execute("SELECT account_id, name FROM pro_player_index WHERE name IS NOT NULL")
    pro_lookup = {}
    for acc_id, name in cur.fetchall():
        normalized = _normalize_name(name)
        if normalized:
            pro_lookup[normalized] = acc_id

    count = 0
    now = datetime.now(timezone.utc).isoformat()

    for player_id, player_name in unmapped:
        normalized = _normalize_name(player_name)
        if normalized not in pro_lookup:
            continue

        cur.execute("""
            SELECT DISTINCT team1 FROM matches
            WHERE player1_1 = ? OR player1_2 = ? OR player1_3 = ?
               OR player1_4 = ? OR player1_5 = ?
            UNION
            SELECT DISTINCT team2 FROM matches
            WHERE player2_1 = ? OR player2_2 = ? OR player2_3 = ?
               OR player2_4 = ? OR player2_5 = ?
        """, (player_id,) * 10)
        teams = [row[0] for row in cur.fetchall() if row[0]]

        for team_name in teams:
            cur.execute(
                """INSERT OR IGNORE INTO player_id_map
                   (player_name, team_name, steam32_id, confidence, searched_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (player_name, team_name, pro_lookup[normalized], 0.95, now),
            )
            count += 1

    conn.commit()
    conn.close()
    state["player_ids_mapped"] = count
    logger.info(f"Bulk-mapped {count} player ID entries.")
    return count


# ─── Resolve our team names to OpenDota team_ids ────────────────────────

def _resolve_our_team_ids():
    conn = _get_conn()
    cur = conn.cursor()
    aliases = _load_team_aliases()

    cur.execute("SELECT team_name FROM teams")
    our_teams = [r[0] for r in cur.fetchall()]

    reverse_aliases = {}
    for alias, canonical in aliases.items():
        reverse_aliases.setdefault(canonical.lower(), set()).add(alias.lower())
        reverse_aliases[canonical.lower()].add(canonical.lower())

    team_map = {}
    for t in our_teams:
        tl = t.lower()
        # Direct match in team_open_data
        cur.execute("SELECT team_id FROM team_open_data WHERE LOWER(name) = ?", (tl,))
        row = cur.fetchone()
        if row:
            team_map[t] = row[0]
            continue
        # Try aliases
        for canonical, alias_set in reverse_aliases.items():
            if tl == canonical or tl in alias_set:
                cur.execute("SELECT team_id FROM team_open_data WHERE LOWER(name) = ?", (canonical,))
                row = cur.fetchone()
                if row:
                    team_map[t] = row[0]
                    break
        if t in team_map:
            continue
        # Try pro_player_index
        cur.execute("SELECT team_id FROM pro_player_index WHERE LOWER(team_name) LIKE ?", (f"%{tl[:20]}%",))
        row = cur.fetchone()
        if row:
            team_map[t] = row[0]

    conn.close()
    return team_map


# ─── Phase 2a: Fetch team match histories ───────────────────────────────

def fetch_team_matches(session, state, team_ids=None):
    logger.info("Phase 2a: Fetching team match histories from OpenDota...")
    now = datetime.now(timezone.utc).isoformat()

    if team_ids is None:
        team_ids = _resolve_our_team_ids()
        team_ids = list(team_ids.items())

    conn = _get_conn()
    cur = conn.cursor()
    total_stored = 0

    for i, (our_name, od_id) in enumerate(team_ids):
        data = _api_get(session, f"/teams/{od_id}/matches")
        if not data:
            time.sleep(SLEEP_BETWEEN)
            continue

        for m in data:
            try:
                cur.execute(
                    """INSERT OR IGNORE INTO team_open_matches
                       (team_id, match_id, duration, start_time, leagueid, league_name,
                        series_id, series_type, radiant, radiant_win, player_count, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        od_id, m.get("match_id"), m.get("duration"), m.get("start_time"),
                        m.get("leagueid"), m.get("league_name"),
                        m.get("series_id"), m.get("series_type"),
                        1 if m.get("radiant") else 0,
                        1 if m.get("radiant_win") else 0,
                        m.get("player_count"), now,
                    ),
                )
                total_stored += 1
            except sqlite3.Error:
                pass

        if (i + 1) % 10 == 0:
            logger.info(f"  Team matches: {i+1}/{len(team_ids)} teams, {total_stored} stored")
            conn.commit()
        time.sleep(SLEEP_BETWEEN)

    conn.commit()
    conn.close()
    state["team_matches_fetched"] = total_stored
    state["teams_enriched"] = len(team_ids)
    logger.info(f"Phase 2a complete: {total_stored} team matches stored for {len(team_ids)} teams.")
    return total_stored


# ─── Phase 2b: Fetch team player rosters ────────────────────────────────

def fetch_team_players(session, state, team_ids=None):
    logger.info("Phase 2b: Fetching team player rosters from OpenDota...")
    now = datetime.now(timezone.utc).isoformat()

    if team_ids is None:
        team_ids = _resolve_our_team_ids()
        team_ids = list(team_ids.items())

    conn = _get_conn()
    cur = conn.cursor()
    total_stored = 0

    for i, (our_name, od_id) in enumerate(team_ids):
        data = _api_get(session, f"/teams/{od_id}/players")
        if not data:
            time.sleep(SLEEP_BETWEEN)
            continue

        for p in data:
            try:
                cur.execute(
                    """INSERT OR IGNORE INTO team_open_players
                       (team_id, account_id, name, country_code, fantasy_role,
                        is_pro, total_earnings, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        od_id, p.get("account_id"), p.get("name"),
                        p.get("country_code"), p.get("fantasy_role"),
                        1 if p.get("is_pro") else 0,
                        p.get("total_earnings"), now,
                    ),
                )
                total_stored += 1
            except sqlite3.Error:
                pass

        if (i + 1) % 10 == 0:
            logger.info(f"  Team players: {i+1}/{len(team_ids)} teams, {total_stored} stored")
            conn.commit()
        time.sleep(SLEEP_BETWEEN)

    conn.commit()
    conn.close()
    state["team_players_fetched"] = total_stored
    logger.info(f"Phase 2b complete: {total_stored} team player entries stored.")
    return total_stored


# ─── Main entry point ───────────────────────────────────────────────────

def run_discovery(phases=None):
    if phases is None:
        phases = [1, 2]

    state = _load_progress()
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    if 1 in phases:
        logger.info("=== Phase 1: Bulk Discovery ===")
        fetch_pro_matches(session, state)
        time.sleep(1)
        fetch_pro_players(session, state)
        time.sleep(1)
        fetch_teams(session, state)
        discover_dota_game_ids(state)
        bulk_map_player_ids(state)

    if 2 in phases:
        logger.info("=== Phase 2: Team Enrichment ===")
        fetch_team_matches(session, state)
        time.sleep(1)
        fetch_team_players(session, state)
        discover_dota_game_ids(state)

    state["last_run"] = datetime.now(timezone.utc).isoformat()
    _save_progress(state)
    logger.info("Discovery complete.")
    return state


def get_status():
    state = _load_progress()
    conn = _get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM pro_match_index")
    pro_matches = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM pro_player_index")
    pro_players = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM team_open_data")
    teams = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM team_open_matches")
    team_matches = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM team_open_players")
    team_players = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM matches WHERE dota_game_id IS NOT NULL")
    dota_game_ids = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM matches")
    total_matches = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM player_id_map WHERE steam32_id IS NOT NULL")
    mapped_players = cur.fetchone()[0]

    conn.close()

    return {
        **state,
        "pro_matches_in_db": pro_matches,
        "pro_players_in_db": pro_players,
        "teams_in_db": teams,
        "team_matches_in_db": team_matches,
        "team_players_in_db": team_players,
        "dota_game_ids": dota_game_ids,
        "total_matches": total_matches,
        "mapped_players": mapped_players,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    result = run_discovery()
    print(json.dumps(result, indent=2))

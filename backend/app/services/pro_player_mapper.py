"""Free local player mapping to avoid OpenDota /api/search calls.

Resolves player names to Steam32 account IDs from data we already have:
  1. pro_player_index  - free /api/proPlayers snapshot (~5k active pros)
  2. match payloads     - account_id + name already fetched for matches

Both paths cost zero API calls. /api/search remains the fallback in the
mappers when neither resolves a name.
"""

import os
import sqlite3
from datetime import datetime, timezone

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "dota2.db")

_LOCAL_INDEX_CONFIDENCE = 0.95
_PAYLOAD_CONFIDENCE = 0.85

_PLAYER_LOOKUP = None


def normalize_name(name):
    if not name:
        return ""
    return name.strip().lower().replace("  ", " ")


def lookup_pro_player_index(conn, player_name):
    """Return account_id from pro_player_index for player_name, or None."""
    normalized = normalize_name(player_name)
    if not normalized:
        return None
    row = conn.execute(
        "SELECT account_id FROM pro_player_index WHERE LOWER(TRIM(name)) = ? LIMIT 1",
        (normalized,),
    ).fetchone()
    return row[0] if row else None


def store_mapping(conn, player_name, team_name, steam32_id, confidence):
    """Upsert a (player_name, team_name) -> steam32_id mapping.

    Fills NULL/unset mappings but never clobbers an existing real one.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO player_id_map (player_name, team_name, steam32_id, confidence, searched_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(player_name, team_name) DO UPDATE SET
               steam32_id  = COALESCE(player_id_map.steam32_id, excluded.steam32_id),
               confidence  = COALESCE(player_id_map.confidence, excluded.confidence),
               searched_at = COALESCE(player_id_map.searched_at, excluded.searched_at)""",
        (player_name, team_name, steam32_id, confidence, now),
    )


def try_local_mapping(conn, player_name, teams):
    """Map player_name locally from pro_player_index for all its teams.

    Returns account_id if mapped (zero API cost), else None.
    """
    account_id = lookup_pro_player_index(conn, player_name)
    if account_id is None:
        return None
    for team_name in (teams or ["Unknown"]):
        store_mapping(conn, player_name, team_name, account_id, _LOCAL_INDEX_CONFIDENCE)
    return account_id


def _get_player_lookup(conn):
    global _PLAYER_LOOKUP
    if _PLAYER_LOOKUP is None:
        lookup = {}
        for player_name in conn.execute("SELECT player_name FROM players").fetchall():
            normalized = normalize_name(player_name[0])
            if normalized:
                lookup.setdefault(normalized, player_name[0])
        _PLAYER_LOOKUP = lookup
    return _PLAYER_LOOKUP


def mine_match_payload(conn, team1, team2, payload_players):
    """Store mappings from a /api/matches payload for names we recognize.

    team1/team2 are our team names for the match. Radiant players (slot < 128)
    are attributed to team1, dire players to team2. Only exact normalized name
    matches are used. Returns number of mappings stored.
    """
    lookup = _get_player_lookup(conn)
    count = 0
    for p in payload_players or []:
        account_id = p.get("account_id")
        name = p.get("name")
        if not account_id or not name:
            continue
        normalized = normalize_name(name)
        if normalized not in lookup:
            continue
        team_name = team1 if int(p.get("player_slot", 0)) < 128 else team2
        store_mapping(conn, lookup[normalized], team_name or "Unknown",
                      account_id, _PAYLOAD_CONFIDENCE)
        count += 1
    return count


def get_mapping_stats(conn=None):
    close = conn is None
    if close:
        conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM player_id_map").fetchone()[0]
    mapped = conn.execute(
        "SELECT COUNT(*) FROM player_id_map WHERE steam32_id IS NOT NULL"
    ).fetchone()[0]
    if close:
        conn.close()
    return {"mappings_total": total, "mappings_mapped": mapped}

"""Incrementally load new matches from all_tiers_games_clean.csv into SQLite.

Non-destructive: only inserts matches (and any new teams/players/tournaments)
that are not already present in the DB. Preserves fetched match_details,
match_player_stats, player_id_map, pro_player_index, team_open_* and existing
fetch_status values. New rows keep fetch_status='pending' so the fetcher daemon
picks them up under the normal quota.

Unlike load_db.py this never calls Base.metadata.drop_all(), so it is safe to
run against a live database that the OpenDota fetcher has been populating.

Run: python -m backend.scripts.refresh_matches [--db PATH] [--csv PATH]
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.database import Base
from backend.app.models.models import Player, Team, Tournament, Match

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_DB = os.path.join(DATA_DIR, "dota2.db")
DEFAULT_CSV = os.path.join(DATA_DIR, "all_tiers_games_clean.csv")
BATCH_SIZE = 5000

DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
DATE_FMT = "%Y-%m-%d"

PLAYER_COL_MAP = {
    f"team{side}_player{slot}_id": f"player{side}_{slot}"
    for side in (1, 2) for slot in range(1, 6)
}


def load_alias_map():
    path = os.path.join(DATA_DIR, "team_aliases.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def apply_aliases(name, alias_map):
    visited = set()
    while name in alias_map and name not in visited:
        visited.add(name)
        name = alias_map[name]
    return name


def load_player_names():
    path = os.path.join(DATA_DIR, "players.csv")
    names = {}
    if not os.path.exists(path):
        return names
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = _int(row.get("player_id"))
            name = (row.get("player_name") or "").strip()
            if pid is not None and name:
                names[pid] = name
    return names


def _int(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if "." in s or "e" in s.lower():
            return int(float(s))
        return int(s)
    except (TypeError, ValueError):
        return None


def _str(value):
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _parse_datetime(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in (DATETIME_FMT, DATE_FMT):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _bool(value):
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in ("1", "true", "yes")


def main():
    parser = argparse.ArgumentParser(description="Incrementally load new matches from the clean CSV.")
    parser.add_argument("--db", default=os.environ.get("DOTA2_DB_PATH", DEFAULT_DB),
                        help="Path to the SQLite database (default: data/dota2.db)")
    parser.add_argument("--csv", default=os.environ.get("DOTA2_CSV_PATH", DEFAULT_CSV),
                        help="Path to all_tiers_games_clean.csv")
    args = parser.parse_args()

    alias_map = load_alias_map()
    player_names = load_player_names()

    engine = create_engine(f"sqlite:///{args.db}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    existing_dota = set()
    existing_pair = set()
    existing_null_gid_mids = set()
    for dota, mid, gid in session.query(Match.dota_game_id, Match.match_id, Match.game_id).all():
        if dota is not None:
            existing_dota.add(dota)
        if mid is not None and gid is not None:
            existing_pair.add((mid, gid))
        if mid is not None and gid is None:
            existing_null_gid_mids.add(mid)
    existing_teams = {r[0] for r in session.query(Team.team_name).all()}
    existing_players = {r[0] for r in session.query(Player.player_id).all()}
    existing_tournaments = {r[0] for r in session.query(Tournament.tournament_id).all()}

    new_teams = set()
    new_players = {}
    new_tournaments = {}
    matches = []
    skipped = 0
    total_added = 0

    with open(args.csv, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            dota = _int(raw.get("dota_game_id"))
            mid = _int(raw.get("match_id"))
            gid = _int(raw.get("game_id"))
            if dota is not None:
                if dota in existing_dota:
                    skipped += 1
                    continue
                existing_dota.add(dota)
            elif mid is not None and gid is not None and (mid, gid) in existing_pair:
                skipped += 1
                continue
            elif dota is None and gid is None and mid is not None and mid in existing_null_gid_mids:
                skipped += 1
                continue

            tid = _int(raw.get("tournament_id"))
            team1 = apply_aliases((raw.get("team1") or "").strip(), alias_map)
            team2 = apply_aliases((raw.get("team2") or "").strip(), alias_map)
            if not team1 or not team2:
                skipped += 1
                continue
            match_datetime = _parse_datetime(raw.get("datetime"))
            if match_datetime is None:
                skipped += 1
                continue

            if team1 not in existing_teams:
                new_teams.add(team1)
            if team2 not in existing_teams:
                new_teams.add(team2)
            if tid is not None and tid not in existing_tournaments:
                name = _str(raw.get("tournament_en"))
                if name:
                    new_tournaments[tid] = name
            for col in PLAYER_COL_MAP:
                pid = _int(raw.get(col))
                if pid is not None and pid not in existing_players and pid in player_names:
                    new_players.setdefault(pid, player_names[pid])

            player_vals = {
                attr: _int(raw.get(col)) for col, attr in PLAYER_COL_MAP.items()
            }
            matches.append(Match(
                tournament_id=tid,
                match_id=mid,
                game_id=gid,
                dota_game_id=dota,
                has_game_data=_bool(raw.get("has_game_data")),
                team1=team1,
                team2=team2,
                score1=_int(raw.get("score1")) or 0,
                score2=_int(raw.get("score2")) or 0,
                best_of=_int(raw.get("bestOf")),
                match_datetime=match_datetime,
                team1_win=_bool(raw.get("team1_win")),
                games_played=_int(raw.get("games_played")),
                **player_vals,
            ))
            total_added += 1

            if len(matches) >= BATCH_SIZE:
                _flush(session, matches, new_teams, new_players, new_tournaments,
                       existing_teams, existing_players, existing_tournaments)
                matches = []
                new_teams = set()
                new_players = {}
                new_tournaments = {}

    _flush(session, matches, new_teams, new_players, new_tournaments,
           existing_teams, existing_players, existing_tournaments)

    session.close()
    print(f"Done. Added {total_added} new matches (skipped {skipped} already present).")


def _flush(session, matches, new_teams, new_players, new_tournaments,
           existing_teams, existing_players, existing_tournaments):
    if new_teams:
        session.bulk_save_objects([Team(team_name=t) for t in sorted(new_teams)])
        existing_teams.update(new_teams)
    if new_players:
        session.bulk_save_objects(
            [Player(player_id=pid, player_name=name) for pid, name in new_players.items()]
        )
        existing_players.update(new_players)
    if new_tournaments:
        session.bulk_save_objects(
            [Tournament(tournament_id=tid, tournament_name=name)
             for tid, name in new_tournaments.items()]
        )
        existing_tournaments.update(new_tournaments)
    if matches:
        session.bulk_save_objects(matches)
    session.commit()


if __name__ == "__main__":
    main()

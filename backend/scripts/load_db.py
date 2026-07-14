"""Load cleaned CSV data into SQLite with team_name as primary key, merging rebrands."""
import pandas as pd
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.database import engine, SessionLocal, Base
from backend.app.models.models import Player, Team, Tournament, Match

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_alias_map():
    path = os.path.join(DATA_DIR, "team_aliases.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def apply_aliases(name, alias_map):
    """Resolve a team name to its canonical name."""
    visited = set()
    while name in alias_map and name not in visited:
        visited.add(name)
        name = alias_map[name]
    return name


def load_players(session):
    df = pd.read_csv(os.path.join(DATA_DIR, "players.csv"))
    df = df.dropna(subset=["player_id", "player_name"])
    df["player_id"] = df["player_id"].astype(int)
    records = [Player(player_id=r["player_id"], player_name=r["player_name"]) for _, r in df.iterrows()]
    session.bulk_save_objects(records)
    session.commit()
    print(f"Loaded {len(records)} players")


def load_teams(session, alias_map):
    df = pd.read_csv(os.path.join(DATA_DIR, "teams.csv"))
    df = df.dropna(subset=["team_id", "team_name"])
    # Resolve all names to canonical, then get unique
    canonical_names = set()
    for name in df["team_name"].unique():
        canonical_names.add(apply_aliases(name, alias_map))
    records = [Team(team_name=name) for name in sorted(canonical_names)]
    session.bulk_save_objects(records)
    session.commit()
    print(f"Loaded {len(records)} unique teams (merged {len(df['team_name'].unique())} -> {len(records)} via aliases)")


def load_tournaments(session):
    df = pd.read_csv(os.path.join(DATA_DIR, "tournaments.csv"))
    records = [Tournament(tournament_id=r["tournament_id"], tournament_name=r["tournament_en"]) for _, r in df.iterrows()]
    session.bulk_save_objects(records)
    session.commit()
    print(f"Loaded {len(records)} tournaments")


def load_matches(session, alias_map):
    df = pd.read_csv(os.path.join(DATA_DIR, "all_tiers_games_clean.csv"))
    df["datetime"] = pd.to_datetime(df["datetime"])

    batch_size = 5000
    records = []
    skipped = 0
    for _, r in df.iterrows():
        team1 = apply_aliases(r["team1"], alias_map)
        team2 = apply_aliases(r["team2"], alias_map)
        if pd.isna(team1) or pd.isna(team2) or not team1 or not team2:
            skipped += 1
            continue

        records.append(Match(
            tournament_id=r["tournament_id"],
            match_id=r["match_id"],
            game_id=r["game_id"] if pd.notna(r["game_id"]) else None,
            dota_game_id=r["dota_game_id"] if pd.notna(r["dota_game_id"]) else None,
            has_game_data=bool(r["has_game_data"]),
            team1=team1,
            team2=team2,
            score1=r["score1"],
            score2=r["score2"],
            best_of=r["bestOf"] if pd.notna(r["bestOf"]) else None,
            match_datetime=r["datetime"],
            team1_win=bool(r["team1_win"]),
            games_played=r["games_played"] if pd.notna(r["games_played"]) else None,
            player1_1=r["team1_player1_id"] if pd.notna(r["team1_player1_id"]) else None,
            player1_2=r["team1_player2_id"] if pd.notna(r["team1_player2_id"]) else None,
            player1_3=r["team1_player3_id"] if pd.notna(r["team1_player3_id"]) else None,
            player1_4=r["team1_player4_id"] if pd.notna(r["team1_player4_id"]) else None,
            player1_5=r["team1_player5_id"] if pd.notna(r["team1_player5_id"]) else None,
            player2_1=r["team2_player1_id"] if pd.notna(r["team2_player1_id"]) else None,
            player2_2=r["team2_player2_id"] if pd.notna(r["team2_player2_id"]) else None,
            player2_3=r["team2_player3_id"] if pd.notna(r["team2_player3_id"]) else None,
            player2_4=r["team2_player4_id"] if pd.notna(r["team2_player4_id"]) else None,
            player2_5=r["team2_player5_id"] if pd.notna(r["team2_player5_id"]) else None,
        ))
        if len(records) >= batch_size:
            session.bulk_save_objects(records)
            session.commit()
            records = []

    if records:
        session.bulk_save_objects(records)
        session.commit()
    print(f"Loaded {len(df) - skipped} matches (skipped {skipped})")


if __name__ == "__main__":
    alias_map = load_alias_map()
    print(f"Loaded {len(alias_map)} team aliases")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        load_players(session)
        load_teams(session, alias_map)
        load_tournaments(session)
        load_matches(session, alias_map)
        print("All data loaded successfully.")
    finally:
        session.close()

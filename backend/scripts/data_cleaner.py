import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")

def clean_all_tiers():
    df = pd.read_csv(os.path.join(DATA_DIR, "all_tiers_games.csv"))
    teams = pd.read_csv(os.path.join(DATA_DIR, "teams.csv"))
    print(f"Original shape: {df.shape}")

    # Drop rows missing critical fields
    df = df.dropna(subset=["score1", "score2", "datetime"])
    print(f"After dropping critical nulls: {df.shape}")

    # Fill missing team names from teams.csv
    teams_clean = teams.dropna(subset=["team_id"]).copy()
    teams_clean["team_id"] = teams_clean["team_id"].astype(int)
    team_map = dict(zip(teams_clean["team_id"], teams_clean["team_name"]))
    df["team1"] = df.apply(
        lambda r: team_map.get(int(r["team1_id"]), r["team1"]) if pd.isna(r["team1"]) and pd.notna(r["team1_id"]) else r["team1"],
        axis=1,
    )
    df["team2"] = df.apply(
        lambda r: team_map.get(int(r["team2_id"]), r["team2"]) if pd.isna(r["team2"]) and pd.notna(r["team2_id"]) else r["team2"],
        axis=1,
    )

    # Drop rows still missing team names (unknown teams)
    df = df.dropna(subset=["team1", "team2"])
    print(f"After filling team names: {df.shape}")

    # Ensure correct types
    df["match_id"] = df["match_id"].astype(int)
    df["game_id"] = df["game_id"].astype("Int64")
    df["dota_game_id"] = df["dota_game_id"].astype("Int64")
    df["score1"] = df["score1"].astype(int)
    df["score2"] = df["score2"].astype(int)
    df["team1_win"] = df["team1_win"].astype(int)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["bestOf"] = df["bestOf"].astype("Int64")
    df["games_played"] = df["games_played"].astype("Int64")

    out_path = os.path.join(DATA_DIR, "all_tiers_games_clean.csv")
    df.to_csv(out_path, index=False)
    print(f"Saved cleaned data: {df.shape} rows -> {out_path}")
    return df


def clean_tier_files():
    for tier in ["tier1", "tier2", "tier3"]:
        path = os.path.join(DATA_DIR, f"{tier}_games.csv")
        df = pd.read_csv(path)
        df = df.dropna(subset=["score1", "score2", "datetime"])
        df = df.dropna(subset=["team1", "team2"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        out = os.path.join(DATA_DIR, f"{tier}_games_clean.csv")
        df.to_csv(out, index=False)
        print(f"{tier}: {df.shape} rows -> {out}")


if __name__ == "__main__":
    clean_all_tiers()
    clean_tier_files()
    print("Done.")

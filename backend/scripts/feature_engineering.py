import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_data():
    df = pd.read_csv(os.path.join(DATA_DIR, "all_tiers_games_clean.csv"))
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def build_team_match_index(df):
    """Build per-team match history index for fast lookups."""
    team_matches = {}
    for idx, row in df.iterrows():
        t1, t2 = row["team1"], row["team2"]
        team_matches.setdefault(t1, []).append((idx, True, row["team1_win"] == 1))
        team_matches.setdefault(t2, []).append((idx, True, row["team1_win"] == 0))
    return team_matches


def compute_features_batch(df, team_matches, tier1_ids, tier2_ids, tier3_ids):
    """Vectorized feature computation using rolling windows."""
    records = []
    total = len(df)

    for i, (_, row) in enumerate(df.iterrows()):
        if i % 5000 == 0:
            print(f"  {i}/{total} ({i*100//total}%)")

        t1, t2 = row["team1"], row["team2"]
        match_date = row["datetime"]

        for team, opponent, won in [(t1, t2, row["team1_win"] == 1), (t2, t1, row["team1_win"] == 0)]:
            hist_indices = team_matches.get(team, [])
            hist_before = [h for h in hist_indices if h[0] < i]

            n = len(hist_before)
            if n == 0:
                records.append({
                    "match_id": row["match_id"], "game_id": row["game_id"],
                    "team": team, "opponent": opponent,
                    "total_matches": 0, "win_rate": 0.5,
                    "recent_5_wr": 0.5, "recent_10_wr": 0.5,
                    "streak": 0, "days_since_last": 0,
                    "h2h_matches": 0, "h2h_wr": 0.5,
                    "tier": row.get("tournament_id", 0),
                })
                continue

            wins = sum(1 for _, _, w in hist_before if w)
            last5 = hist_before[-5:]
            last10 = hist_before[-10:]
            last5_wins = sum(1 for _, _, w in last5 if w)
            last10_wins = sum(1 for _, _, w in last10 if w)

            streak = 0
            for _, _, w in reversed(hist_before):
                if streak == 0:
                    streak = 1 if w else -1
                elif (streak > 0 and w) or (streak < 0 and not w):
                    streak += 1 if streak > 0 else -1
                else:
                    break

            last_idx = hist_before[-1][0]
            last_date = df.iloc[last_idx]["datetime"]
            days_since = (match_date - last_date).days

            # Head-to-head
            h2h = [h for h in hist_before if df.iloc[h[0]]["team1"] == opponent or df.iloc[h[0]]["team2"] == opponent]
            h2h_wins = sum(1 for _, _, w in h2h if w)

            records.append({
                "match_id": row["match_id"], "game_id": row["game_id"],
                "team": team, "opponent": opponent,
                "total_matches": n, "win_rate": wins / n,
                "recent_5_wr": last5_wins / len(last5),
                "recent_10_wr": last10_wins / len(last10),
                "streak": streak,
                "days_since_last": days_since,
                "h2h_matches": len(h2h), "h2h_wr": h2h_wins / len(h2h) if h2h else 0.5,
                "tier": (
                    1 if row["tournament_id"] in tier1_ids else
                    2 if row["tournament_id"] in tier2_ids else
                    3 if row["tournament_id"] in tier3_ids else 0
                ),
            })

    return pd.DataFrame(records)


def pivot_features(features):
    """Pivot team features so each match gets one row with both teams' features."""
    results = []
    for mid, group in features.groupby("match_id"):
        if len(group) < 2:
            continue
        row = group.iloc[0]
        team_row = group[group["team"] == row["team"]].iloc[0]
        opp_row = group[group["team"] == row["opponent"]].iloc[0]

        prefix = lambda p, col: f"{p}_{col}"
        record = {"match_id": mid, "game_id": row["game_id"],
                   "team": team_row["team"], "opponent": team_row["opponent"],
                   "tier": team_row["tier"]}
        for col in ["total_matches", "win_rate", "recent_5_wr", "recent_10_wr",
                     "streak", "days_since_last", "h2h_matches", "h2h_wr"]:
            record[f"team_{col}"] = team_row[col]
            record[f"opp_{col}"] = opp_row[col]

        results.append(record)

    return pd.DataFrame(results)


if __name__ == "__main__":
    df = load_data()

    t1 = pd.read_csv(os.path.join(DATA_DIR, "tier1_games_clean.csv"))
    t2 = pd.read_csv(os.path.join(DATA_DIR, "tier2_games_clean.csv"))
    t3 = pd.read_csv(os.path.join(DATA_DIR, "tier3_games_clean.csv"))
    tier1_ids = set(t1["tournament_id"].unique())
    tier2_ids = set(t2["tournament_id"].unique())
    tier3_ids = set(t3["tournament_id"].unique())

    print(f"Building team index for {len(df)} rows...")
    team_matches = build_team_match_index(df)

    print("Computing features...")
    features = compute_features_batch(df, team_matches, tier1_ids, tier2_ids, tier3_ids)
    out_path = os.path.join(DATA_DIR, "team_features.csv")
    features.to_csv(out_path, index=False)
    print(f"Saved raw features: {features.shape} -> {out_path}")

    print("Pivoting features...")
    pivoted = pivot_features(features)
    pivot_path = os.path.join(DATA_DIR, "match_features.csv")
    pivoted.to_csv(pivot_path, index=False)
    print(f"Saved match features: {pivoted.shape} -> {pivot_path}")

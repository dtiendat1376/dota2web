"""Detect team rebrands - stricter: 4+ shared players, different time periods."""
import pandas as pd
import os
import sys
import json
from collections import defaultdict

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
DATA_DIR = os.path.join(BASE_DIR, "data")

player_cols_t1 = ['team1_player1_id','team1_player2_id','team1_player3_id','team1_player4_id','team1_player5_id']
player_cols_t2 = ['team2_player1_id','team2_player2_id','team2_player3_id','team2_player4_id','team2_player5_id']


def find_rebrands(df, min_shared=4):
    # For each team, find their most-used roster + active date range
    team_rosters = defaultdict(lambda: defaultdict(int))
    team_dates = defaultdict(list)

    for _, row in df.iterrows():
        for pcols, tcol in [(player_cols_t1, 'team1'), (player_cols_t2, 'team2')]:
            players = tuple(sorted(int(row[c]) for c in pcols if pd.notna(row[c])))
            team = row[tcol]
            if len(players) >= 3:
                team_rosters[team][players] += 1
            team_dates[team].append(row['datetime'])

    # Best roster per team
    team_best = {}
    team_range = {}
    for team in team_rosters:
        best = max(team_rosters[team], key=team_rosters[team].get)
        team_best[team] = set(best)
        dates = sorted(team_dates[team])
        team_range[team] = (dates[0], dates[-1])

    # Compare teams - only if they don't overlap much in time
    teams = list(team_best.keys())
    pairs = []

    for i in range(len(teams)):
        for j in range(i + 1, len(teams)):
            t1, t2 = teams[i], teams[j]
            shared = team_best[t1] & team_best[t2]
            if len(shared) < min_shared:
                continue

            # Check temporal separation - teams should be active at different times
            r1_start, r1_end = team_range[t1]
            r2_start, r2_end = team_range[t2]

            # Allow some overlap (6 months) but not full overlap
            overlap_days = (min(r1_end, r2_end) - max(r1_start, r2_start)).days
            total_span = (max(r1_end, r2_end) - min(r1_start, r2_start)).days
            overlap_ratio = overlap_days / total_span if total_span > 0 else 1

            if overlap_ratio < 0.7:  # Less than 70% time overlap = likely rebrand
                pairs.append((t1, t2, len(shared)))

    return pairs


def merge_rebrands(pairs):
    parent = {}
    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for t1, t2, _ in pairs:
        union(t1, t2)

    groups = defaultdict(set)
    for t1, t2, _ in pairs:
        root = find(t1)
        groups[root].add(t1)
        groups[root].add(t2)
    return groups


def pick_canonical(group, df):
    counts = {}
    for name in group:
        counts[name] = len(df[(df['team1'] == name) | (df['team2'] == name)])
    return max(counts, key=counts.get)


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    df = pd.read_csv(os.path.join(DATA_DIR, "all_tiers_games_clean.csv"))
    df["datetime"] = pd.to_datetime(df["datetime"])

    print("Finding rebrands (4+ shared players, temporal check)...")
    pairs = find_rebrands(df, min_shared=4)
    print(f"Found {len(pairs)} valid rebrand pairs")

    groups = merge_rebrands(pairs)
    print(f"Merged into {len(groups)} groups")

    alias_map = {}
    for root, group in groups.items():
        canonical = pick_canonical(group, df)
        for name in group:
            if name != canonical:
                alias_map[name] = canonical

    out_path = os.path.join(DATA_DIR, "team_aliases.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(alias_map, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(alias_map)} aliases")

    for root, group in sorted(groups.items(), key=lambda x: -len(x[1]))[:25]:
        canonical = pick_canonical(group, df)
        aliases = sorted(group - {canonical})
        total = sum(len(df[(df['team1'] == n) | (df['team2'] == n)]) for n in group)
        print(f"  {canonical:30s} ({total:5d}) <- {', '.join(aliases)}")

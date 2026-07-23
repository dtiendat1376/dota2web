"""
Add performance indexes and new tables to dota2.db.

Run: python -m backend.scripts.add_indexes
"""
import sqlite3
import time
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "dota2.db")


TABLES = [
    # Player ID mapping table (Steam32 ID mapping)
    """CREATE TABLE IF NOT EXISTS player_id_map (
        player_name TEXT NOT NULL,
        team_name TEXT NOT NULL,
        steam32_id INTEGER,
        confidence REAL,
        searched_at TEXT,
        PRIMARY KEY (player_name, team_name)
    )""",
]

INDEXES = [
    # Player column indexes (critical — eliminates full table scans for player queries)
    ("idx_m_p1_1", "matches", "player1_1"),
    ("idx_m_p1_2", "matches", "player1_2"),
    ("idx_m_p1_3", "matches", "player1_3"),
    ("idx_m_p1_4", "matches", "player1_4"),
    ("idx_m_p1_5", "matches", "player1_5"),
    ("idx_m_p2_1", "matches", "player2_1"),
    ("idx_m_p2_2", "matches", "player2_2"),
    ("idx_m_p2_3", "matches", "player2_3"),
    ("idx_m_p2_4", "matches", "player2_4"),
    ("idx_m_p2_5", "matches", "player2_5"),
    # Tournament FK index (critical — tournament detail/listing/standings)
    ("idx_m_tournament", "matches", "tournament_id"),
    # Team individual indexes (high — team OR queries)
    ("idx_m_team1", "matches", "team1"),
    ("idx_m_team2", "matches", "team2"),
    # Predictions FK index (medium)
    ("idx_pred_match", "predictions", "match_id"),
    # OpenDota fetched data indexes
    ("idx_md_game_id", "match_details", "dota_game_id"),
    ("idx_mps_game_id", "match_player_stats", "dota_game_id"),
    ("idx_mps_hero", "match_player_stats", "hero_id"),
    # Player ID map indexes
    ("idx_pim_steam32", "player_id_map", "steam32_id"),
]

DROP_INDEX = "ix_matches_match_datetime"  # duplicate of idx_matches_datetime


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Create new tables
    print("Creating new tables...")
    for sql in TABLES:
        print(f"  Creating table...", end=" ")
        t0 = time.time()
        cur.execute(sql)
        elapsed = time.time() - t0
        print(f"done ({elapsed:.2f}s)")

    # Drop duplicate index
    print(f"Removing duplicate index '{DROP_INDEX}'...")
    try:
        cur.execute(f"DROP INDEX IF EXISTS {DROP_INDEX}")
        print(f"  Dropped.")
    except Exception as e:
        print(f"  Skip: {e}")

    # Create indexes
    for idx_name, table, column in INDEXES:
        print(f"Creating {idx_name} on {table}({column})...", end=" ")
        t0 = time.time()
        cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
        elapsed = time.time() - t0
        print(f"done ({elapsed:.2f}s)")

    conn.commit()

    # ANALYZE for query planner stats
    print("Running ANALYZE...", end=" ")
    t0 = time.time()
    cur.execute("ANALYZE")
    conn.commit()
    elapsed = time.time() - t0
    print(f"done ({elapsed:.2f}s)")

    # List all indexes
    print("\nAll indexes:")
    cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' ORDER BY tbl_name, name")
    for name, table, sql in cur.fetchall():
        print(f"  {name} -> {table}")

    # Row counts
    for table in ["matches", "players", "teams", "tournaments", "predictions", "match_details", "match_player_stats", "heroes", "player_id_map"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"\n  {table}: {count} rows")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()

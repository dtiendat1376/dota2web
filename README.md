# Dota 2 Pro Matches

A full-stack analytics dashboard for Dota 2 professional match history, built with FastAPI + React + SQLite. Features 81,000+ matches, 67 teams, 11,500+ players, and 1,200+ tournaments spanning 2013–2026.

## Features

- **Dashboard** — Global stats, top teams leaderboard, recent matches
- **Matches** — Searchable match list with pagination and team filtering
- **Teams** — Leaderboard with 38-feature team profiles: win rate, form, streaks, format performance, current lineup, slot win rates
- **Players** — Player search with career stats, team history, and tournament wins
- **Tournaments** — Tier inference, champion/runner-up detection, group/playoff standings
- **H2H & Predictions** — Head-to-head analysis with win rate bars, recent form, and a match outcome prediction model
- **Lineup Builder** — Select 5 players by position, analyze pair synergy matrix, exact lineup history, and similar lineups

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, SQLAlchemy |
| Frontend | React 19, React Router 7, Axios |
| Database | SQLite (`data/dota2.db`, 34MB) |
| Dataset | [ektarr/dota-2-pro-matches](https://www.kaggle.com/datasets/ektarr/dota-2-pro-matches) (Kaggle) |

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm

### 1. Install dependencies

```bash
# Backend
pip install fastapi uvicorn sqlalchemy

# Frontend
cd frontend
npm install
cd ..
```

### 2. Start the servers

Open two terminals from the project root:

**Terminal 1 — Backend (port 8000):**

```bash
uvicorn backend.app.main:app --reload --port 8000
```

**Terminal 2 — Frontend (port 3000):**

```bash
cd frontend
npm start
```

### 3. Open the app

Navigate to [http://localhost:3000](http://localhost:3000).

### Health check

Verify the backend is running:

```bash
curl http://localhost:8000/api/stats
```

You should see:

```json
{
  "total_matches": 81886,
  "total_players": 11508,
  "total_teams": 67,
  "total_tournaments": 1242
}
```

## Database Setup

The pre-built SQLite database is at `data/dota2.db`. To rebuild it from scratch:

```bash
pip install kagglehub pandas
python fetch_and_update.py
```

This runs the full pipeline:

1. Downloads CSVs from Kaggle via `kagglehub`
2. `data_cleaner.py` — Cleans and deduplicates game rows
3. `detect_rebrands.py` — Detects team renames/merges (262 aliases)
4. `load_db.py` — Loads data into SQLite with foreign keys
5. `add_indexes.py` — Adds 14 performance indexes and runs ANALYZE

Alternatively, run individual steps:

```bash
python backend/scripts/data_cleaner.py
python backend/scripts/detect_rebrands.py
python backend/scripts/load_db.py
python -m backend.scripts.add_indexes
```

## Project Structure

```
dota2web/
├── data/
│   ├── dota2.db                    # SQLite database
│   ├── all_tiers_games_clean.csv   # Cleaned match data
│   ├── players.csv                 # 11,508 players
│   ├── tournaments.csv             # 1,242 tournaments
│   └── team_aliases.json           # 262 team rename mappings
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app (v2.0.0)
│   │   ├── database.py             # SQLite connection
│   │   ├── models/
│   │   │   └── models.py           # SQLAlchemy models
│   │   ├── routes/
│   │   │   ├── matches.py          # Match listing, search, detail
│   │   │   ├── teams.py            # Team list, leaderboard, profile
│   │   │   ├── players.py          # Player search and profile
│   │   │   ├── predictions.py      # Match prediction endpoint
│   │   │   ├── tournaments.py      # Tournament list, detail, standings
│   │   │   ├── h2h.py              # Head-to-head analysis
│   │   │   └── lineup.py           # Lineup analysis and similarity
│   │   └── services/
│   │       ├── team_features.py    # 38-feature team profile
│   │       ├── player_features.py  # 20-feature player profile
│   │       ├── tournament_features.py  # Tier inference, champions, standings
│   │       ├── h2h_features.py     # Head-to-head calculations
│   │       ├── lineup_features.py  # Lineup synergy and similarity
│   │       └── prediction.py       # Prediction model (feature-based)
│   └── scripts/
│       ├── data_cleaner.py         # CSV cleaning pipeline
│       ├── detect_rebrands.py      # Team rename detection
│       ├── load_db.py              # CSV to SQLite loader
│       └── add_indexes.py          # Performance index creation
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.js                  # Router with 7 tabs
│   │   ├── App.css                 # Dark theme styles
│   │   ├── api.js                  # Axios API client
│   │   └── pages/
│   │       ├── Dashboard.js        # Stats + leaderboard
│   │       ├── Matches.js          # Match search + list
│   │       ├── Teams.js            # Team leaderboard + profile
│   │       ├── Players.js          # Player search + profile
│   │       ├── Tournaments.js      # Tournament list + detail + standings
│   │       ├── H2HPredict.js       # H2H + prediction tabs
│   │       └── LineupBuilder.js    # 5-slot player selector + analysis
│   └── package.json
└── fetch_and_update.py             # Full pipeline: download + build DB
```

## API Reference

### Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Global stats (matches, teams, players, tournaments) |

### Matches

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/matches/` | List matches (params: `limit`, `offset`, `team`) |
| GET | `/api/matches/{match_id}` | Match detail with game IDs |
| GET | `/api/matches/team/{name}/stats` | Team match stats |

### Teams

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/teams/` | List all teams |
| GET | `/api/teams/leaderboard` | Win rate leaderboard (params: `limit`) |
| GET | `/api/teams/{name}` | Full team profile (38 features) |
| GET | `/api/teams/{name}/lineup` | Current 5-man lineup |

### Players

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/players/` | Search players (params: `search`, `limit`, `offset`) |
| GET | `/api/players/{player_id}` | Full player profile (20 features) |
| GET | `/api/players/{player_id}/teams` | Player team history |

### Tournaments

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tournaments/` | List tournaments (params: `limit`, `offset`, `search`) |
| GET | `/api/tournaments/{id}` | Tournament detail with format breakdown |
| GET | `/api/tournaments/{id}/standings` | Group and playoff standings |

### Head-to-Head & Predictions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/h2h/` | H2H analysis (body: `{ team1, team2 }`) |
| POST | `/api/predictions/predict` | Match prediction (body: `{ team1, team2 }`) |
| GET | `/api/predictions/history` | Prediction history |

### Lineup Builder

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/lineup/analyze` | Analyze 5-player lineup (body: `{ player_ids: [int] }`) |
| POST | `/api/lineup/similar` | Find similar historical lineups |

## Data Pipeline

The dataset is a Kaggle collection of Dota 2 pro match CSVs. Each CSV row represents one **game** within a series (e.g., Game 1 of a Bo3).

Key data points per match:
- Teams, scores, winner, best-of format, date
- 10 player IDs (5 per team, slot-consistent)
- Tournament ID, match ID, Dota game ID

**Not in the dataset:** K/D/A, heroes, GPM, game duration. These require the OpenDota API using the stored `dota_game_id` values (53,957 unique game IDs available).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REACT_APP_API_URL` | `http://localhost:8000` | Backend API base URL |

Set via `.env` in `frontend/` or export before `npm start`:

```bash
REACT_APP_API_URL=http://localhost:8000 npm start
```

## License

Data sourced from [Kaggle](https://www.kaggle.com/datasets/ektarr/dota-2-pro-matches). Application code is provided as-is.

# Dota 2 Pro Matches Dashboard

A full-stack analytics platform for Dota 2 professional match history. Built with **FastAPI + React 19 + SQLite**, it covers 81,000+ matches, 67 teams, 11,500+ players, and 1,200+ tournaments from 2013 to 2026.

## Features

| Tab | What it does |
|-----|-------------|
| **Dashboard** | Global stats, top teams leaderboard, recent matches, OpenDota fetch progress, hero verification results |
| **Matches** | Paginated match list with team search, score display, and full game detail view (draft, per-player stats) |
| **Teams** | Leaderboard and 38-feature team profiles: win rate, form, streaks, format performance, roster era analysis, current lineup, hero pool, slot win rates |
| **Players** | Player search with career stats, team history, tournament wins, and live OpenDota career data |
| **Tournaments** | Tier inference, champion/runner-up detection, group & playoff standings |
| **Heroes** | Hero list sorted by pick count, win rate, kills, or GPM. Filterable by attribute. Detailed stats per hero. |
| **H2H & Predictions** | Head-to-head analysis with win rate bars, recent form, and a feature-engineered prediction model with backtesting |
| **Lineup Builder** | Select 5 players by position, analyze pair synergy matrix, exact lineup history, and similar historical lineups |
| **Global Search** | Navbar search across teams, players, and matches |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, SQLAlchemy, Pydantic |
| Frontend | React 19, React Router 7, Axios |
| Database | SQLite (`data/dota2.db`, ~34 MB) |
| External API | [OpenDota API](https://docs.opendota.com/) (background fetcher for match details, player stats, hero data) |
| Dataset | [ektarr/dota-2-pro-matches](https://www.kaggle.com/datasets/ektarr/dota-2-pro-matches) (Kaggle) |

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- npm

### 1. Install dependencies

```bash
pip install -r requirements.txt

cd frontend && npm install && cd ..
```

### 2. Start the servers

Open two terminals from the project root:

**Terminal 1 — Backend (port 8000):**

```bash
uvicorn backend.app.main:app --reload --port 8000
```

**Terminal 2 — Frontend (port 3000):**

```bash
cd frontend && npm start
```

### 3. Open the app

Navigate to [http://localhost:3000](http://localhost:3000).

### Health check

```bash
curl http://localhost:8000/api/stats
```

Expected:

```json
{
  "total_matches": 81886,
  "total_players": 11508,
  "total_teams": 67,
  "total_tournaments": 1242
}
```

## Database Setup

The pre-built SQLite database is at `data/dota2.db`. To rebuild from scratch:

```bash
pip install kagglehub pandas
python fetch_and_update.py
```

This runs the full pipeline:

1. Downloads CSVs from Kaggle via `kagglehub`
2. **`data_cleaner.py`** — Cleans and deduplicates game rows
3. **`detect_rebrands.py`** — Detects team renames/merges (262 aliases via union-find on shared rosters)
4. **`load_db.py`** — Loads data into SQLite with foreign keys
5. **`add_indexes.py`** — Adds 17 performance indexes and runs ANALYZE

Or run individual steps:

```bash
python backend/scripts/data_cleaner.py
python backend/scripts/detect_rebrands.py
python backend/scripts/load_db.py
python -m backend.scripts.add_indexes
```

### OpenDota Fetcher

A background daemon starts automatically with the FastAPI server. It fetches match details (drafts, per-player stats) from the OpenDota API and maps player names to Steam32 IDs.

- **Rate limit:** 2,950 calls/day; the fetcher gets the largest slice, the mapper a small cap (local pro-player index covers most names), and live/utility calls a hard cap
- **Retries:** Failed matches retry up to a bounded number of times, then are retired permanently to avoid wasting quota on dead game IDs
- **Progress:** Tracked in `data/opendota_progress.json` and `data/api_quota.json`
- **Verification:** Cross-validates local hero win rates against OpenDota `/heroStats`

## Project Structure

```
dota2web/
├── data/
│   ├── dota2.db                       # SQLite database
│   ├── all_tiers_games_clean.csv      # Cleaned match data
│   ├── players.csv                    # 11,508 players
│   ├── tournaments.csv                # 1,242 tournaments
│   └── team_aliases.json              # 262 team rename mappings
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app (v3.0.0)
│   │   ├── database.py                # SQLite connection
│   │   ├── models/
│   │   │   └── models.py              # SQLAlchemy models (10 tables)
│   │   ├── routes/
│   │   │   ├── matches.py             # Match listing, search, detail
│   │   │   ├── teams.py               # Team list, leaderboard, profile
│   │   │   ├── players.py             # Player search and profile
│   │   │   ├── predictions.py         # Prediction + backtesting
│   │   │   ├── tournaments.py         # Tournament list, detail, standings
│   │   │   ├── h2h.py                 # Head-to-head analysis
│   │   │   ├── lineup.py              # Lineup analysis and similarity
│   │   │   ├── heroes.py              # Hero stats and detail
│   │   │   ├── search.py              # Global search
│   │   │   └── verification.py        # Hero stats cross-validation
│   │   └── services/
│   │       ├── team_features.py       # 38-feature team profile
│   │       ├── player_features.py     # 20-feature player profile
│   │       ├── tournament_features.py # Tier inference, champions, standings
│   │       ├── h2h_features.py        # Head-to-head calculations
│   │       ├── lineup_features.py     # Lineup synergy and similarity
│   │       ├── prediction.py          # Prediction model (v2.0)
│   │       ├── hero_features.py       # Hero aggregation and stats
│   │       ├── team_hero_features.py  # Team hero pool
│   │       └── fetch_status.py        # OpenDota daemon status
│   └── scripts/
│       ├── data_cleaner.py            # CSV cleaning pipeline
│       ├── detect_rebrands.py         # Team rename detection
│       ├── load_db.py                 # CSV to SQLite loader
│       ├── add_indexes.py             # Performance index creation
│       ├── fetch_opendota.py          # Background OpenDota fetcher
│       ├── map_player_ids.py          # Player ID mapping
│       ├── verify_hero_stats.py       # Hero stats verification
│       └── feature_engineering.py     # Offline feature computation
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.js                     # Router with 8 tabs + global search
│   │   ├── App.css                    # Dark theme styles
│   │   ├── api.js                     # Axios API client (20+ functions)
│   │   ├── components/
│   │   │   └── SearchBar.js           # Global navbar search
│   │   └── pages/
│   │       ├── Dashboard.js           # Stats + leaderboard + fetch progress
│   │       ├── Matches.js             # Match search + list
│   │       ├── MatchDetail.js         # Full game detail view
│   │       ├── Teams.js               # Team leaderboard + profile
│   │       ├── Players.js             # Player search + profile
│   │       ├── Tournaments.js         # Tournament list + detail + standings
│   │       ├── H2HPredict.js          # H2H + prediction tabs
│   │       ├── HeroAnalytics.js       # Hero list + detail
│   │       └── LineupBuilder.js       # 5-slot player selector + analysis
│   └── package.json
├── fetch_and_update.py                # Full pipeline: download + build DB
├── requirements.txt
└── .env
```

## API Reference

### Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Global stats (matches, teams, players, tournaments) |
| GET | `/api/search?q=` | Global search across teams, players, matches |
| GET | `/api/fetch/status` | OpenDota fetcher daemon status |

### Matches

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/matches/` | List matches (params: `limit`, `offset`, `team`) |
| GET | `/api/matches/{match_id}` | Basic match info |
| GET | `/api/matches/{match_id}/detail` | Full game detail (drafts, per-player stats) |
| GET | `/api/matches/team/{name}/stats` | Team match stats |

### Teams

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/teams/` | List all teams |
| GET | `/api/teams/leaderboard` | Win rate leaderboard (params: `limit`) |
| GET | `/api/teams/{name}` | Full team profile (38 features) |
| GET | `/api/teams/{name}/lineup` | Current 5-man lineup |
| GET | `/api/teams/{name}/heroes` | Top 20 hero pool |

### Players

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/players/` | Search players (params: `search`, `team`, `limit`, `offset`, `min_matches`) |
| GET | `/api/players/{id}` | Full player profile (20 features) |
| GET | `/api/players/{id}/teams` | Player team history |
| GET | `/api/players/{id}/steam32` | Steam32 ID mapping |
| GET | `/api/players/{id}/career` | Live OpenDota career data |

### Tournaments

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tournaments/` | List tournaments (params: `limit`, `offset`, `search`) |
| GET | `/api/tournaments/{id}` | Tournament detail with format breakdown |
| GET | `/api/tournaments/{id}/standings` | Group and playoff standings |

### Heroes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/heroes/` | Hero list (params: `sort`, `attr`) |
| GET | `/api/heroes/{hero_id}` | Hero detail stats |
| GET | `/api/heroes/{hero_id}/matches` | Recent matches with hero |

### Head-to-Head & Predictions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/h2h/` | H2H analysis (body: `{ team1, team2 }`) |
| POST | `/api/predictions/predict` | Match prediction (body: `{ team1, team2, match_id? }`) |
| POST | `/api/predictions/backtest` | Backtest on historical H2H (body: `{ team1, team2, limit? }`) |
| GET | `/api/predictions/history` | Recent matches with game data |

### Lineup Builder

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/lineup/analyze` | Analyze 5-player lineup (body: `{ player_ids: [int] }`) |
| POST | `/api/lineup/similar` | Find similar historical lineups |

### Verification

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/verification/status` | Last hero verification results |
| POST | `/api/verification/run` | Trigger hero stats cross-validation |

## Prediction Model

The prediction model (`v2.0`) is a **feature-engineered heuristic** — no ML training, no external libraries. It uses a weighted scoring system based on team features and head-to-head data.

**Key signals by weight:**

| Signal | Weight | Description |
|--------|--------|-------------|
| Roster decay WR | 0.25 | Exponential time-decay win rate (`e^(-0.05 * days_old)`) |
| Overall win rate | 0.12 | All-time win rate |
| H2H recent 10 WR | 0.10 | Last 10 head-to-head win rate |
| Bo3 win rate | 0.08 | Best-of-3 performance |
| Series length WR | 0.05 | Performance in series vs. singles |
| H2H score diff | 0.05 | Average score differential in H2H |
| Streak, frequency, stability | 0.02–0.04 | Momentum and activity signals |

Final probability is computed via **sigmoid** on the score difference, clamped to [0.05, 0.95]. Confidence is derived from distance from 50-50, data availability, and roster overlap.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REACT_APP_API_URL` | `http://localhost:8000` | Backend API base URL |
| `CORS_ORIGIN` | `http://localhost:3000` | Allowed CORS origin |

Set via `.env` in `frontend/` or export before `npm start`:

```bash
REACT_APP_API_URL=http://localhost:8000 npm start
```

## License

Data sourced from [Kaggle](https://www.kaggle.com/datasets/ektarr/dota-2-pro-matches). Application code is provided as-is.

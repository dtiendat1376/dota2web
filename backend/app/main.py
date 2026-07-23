from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
import threading
import os

from backend.app.database import get_db
from backend.app.models.models import Match, Player, Team, Tournament
from backend.app.routes import matches, teams, players, predictions, tournaments, h2h, lineup, heroes, search, verification


@asynccontextmanager
async def lifespan(app):
    from backend.app.services.fetch_status import start_fetcher
    thread = threading.Thread(target=start_fetcher, daemon=True)
    thread.start()
    yield


app = FastAPI(title="Dota 2 Pro Matches API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches.router, prefix="/api/matches", tags=["matches"])
app.include_router(teams.router, prefix="/api/teams", tags=["teams"])
app.include_router(players.router, prefix="/api/players", tags=["players"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(tournaments.router, prefix="/api/tournaments", tags=["tournaments"])
app.include_router(h2h.router, prefix="/api/h2h", tags=["h2h"])
app.include_router(lineup.router, prefix="/api/lineup", tags=["lineup"])
app.include_router(heroes.router, prefix="/api/heroes", tags=["heroes"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(verification.router, prefix="/api/verification", tags=["verification"])


@app.get("/")
def root():
    return {"message": "Dota 2 Pro Matches API"}


@app.get("/api/stats")
def overview_stats(db: Session = Depends(get_db)):
    return {
        "total_matches": db.query(func.count(func.distinct(Match.match_id))).scalar(),
        "total_players": db.query(func.count(Player.player_id)).scalar(),
        "total_teams": db.query(func.count(Team.team_name)).scalar(),
        "total_tournaments": db.query(func.count(Tournament.tournament_id)).scalar(),
    }


@app.get("/api/fetch/status")
def fetch_status():
    from backend.scripts.fetch_opendota import get_status
    return get_status()

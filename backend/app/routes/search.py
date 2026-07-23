from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
from backend.app.database import get_db
from backend.app.models.models import Team, Player, Match

router = APIRouter()


@router.get("/")
def global_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    pattern = f"%{q}%"

    teams = (
        db.query(Team)
        .filter(Team.team_name.ilike(pattern))
        .limit(limit)
        .all()
    )

    players = (
        db.query(Player)
        .filter(Player.player_name.ilike(pattern))
        .limit(limit)
        .all()
    )

    match_filter = (Match.team1.ilike(pattern)) | (Match.team2.ilike(pattern))
    if q.isdigit():
        match_filter = match_filter | (Match.match_id == int(q)) | (Match.dota_game_id == int(q))

    matches = (
        db.query(Match)
        .filter(match_filter)
        .order_by(Match.match_datetime.desc())
        .limit(limit)
        .all()
    )

    return {
        "teams": [
            {"name": t.team_name, "type": "team"}
            for t in teams
        ],
        "players": [
            {"name": p.player_name, "id": p.player_id, "type": "player"}
            for p in players
        ],
        "matches": [
            {
                "id": m.match_id,
                "team1": m.team1,
                "team2": m.team2,
                "score": f"{m.score1}-{m.score2}",
                "date": m.match_datetime.isoformat() if m.match_datetime else None,
                "type": "match",
            }
            for m in matches
        ],
    }

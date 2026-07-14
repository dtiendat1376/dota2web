from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional

from backend.app.database import get_db
from backend.app.models.models import Match, Team, Tournament

router = APIRouter()


@router.get("/")
def list_matches(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    team: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Match, Tournament.tournament_name).join(
        Tournament, Match.tournament_id == Tournament.tournament_id, isouter=True
    )

    if team:
        query = query.filter(
            (Match.team1.ilike(f"%{team}%")) | (Match.team2.ilike(f"%{team}%"))
        )

    total = db.query(Match).filter(
        (Match.team1.ilike(f"%{team}%")) | (Match.team2.ilike(f"%{team}%"))
    ).count() if team else db.query(func.count(Match.id)).scalar()

    rows = query.order_by(desc(Match.match_datetime)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "matches": [
            {
                "match_id": m.match_id,
                "game_id": m.game_id,
                "tournament": t_name or "Unknown",
                "team1": m.team1,
                "team2": m.team2,
                "score1": m.score1,
                "score2": m.score2,
                "best_of": m.best_of,
                "datetime": m.match_datetime.isoformat() if m.match_datetime else None,
                "team1_win": m.team1_win,
            }
            for m, t_name in rows
        ],
    }


@router.get("/team/{team_name}/stats")
def team_stats(team_name: str, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.team_name.ilike(f"%{team_name}%")).first()
    if not team:
        return {"error": "Team not found"}

    name = team.team_name
    matches = db.query(Match).filter(
        (Match.team1 == name) | (Match.team2 == name)
    ).order_by(desc(Match.match_datetime)).all()

    if not matches:
        return {"team": name, "total_matches": 0}

    wins = sum(1 for m in matches if (m.team1 == name and m.team1_win) or (m.team2 == name and not m.team1_win))

    recent_5 = []
    for m in matches[:5]:
        opponent = m.team2 if m.team1 == name else m.team1
        won = (m.team1 == name and m.team1_win) or (m.team2 == name and not m.team1_win)
        recent_5.append({
            "match_id": m.match_id,
            "opponent": opponent,
            "won": won,
            "score": f"{m.score1}-{m.score2}",
            "datetime": m.match_datetime.isoformat() if m.match_datetime else None,
        })

    return {
        "team": name,
        "total_matches": len(matches),
        "wins": wins,
        "losses": len(matches) - wins,
        "win_rate": round(wins / len(matches), 4),
        "recent_5": recent_5,
    }


@router.get("/{match_id}")
def get_match(match_id: int, db: Session = Depends(get_db)):
    m = db.query(Match).filter(Match.match_id == match_id).first()
    if not m:
        return {"error": "Match not found"}

    t = db.query(Tournament).filter(Tournament.tournament_id == m.tournament_id).first()

    return {
        "match_id": m.match_id,
        "game_id": m.game_id,
        "dota_game_id": m.dota_game_id,
        "has_game_data": m.has_game_data,
        "tournament": t.tournament_name if t else "Unknown",
        "team1": m.team1,
        "team2": m.team2,
        "score1": m.score1,
        "score2": m.score2,
        "best_of": m.best_of,
        "datetime": m.match_datetime.isoformat() if m.match_datetime else None,
        "team1_win": m.team1_win,
        "games_played": m.games_played,
    }

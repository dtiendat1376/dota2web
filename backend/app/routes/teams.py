from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, case, func, select, union_all

from backend.app.database import get_db
from backend.app.models.models import Team, Match, Player, Tournament
from backend.app.services.team_features import get_team_features

router = APIRouter()


@router.get("/")
def list_teams(db: Session = Depends(get_db)):
    teams = db.query(Team).all()
    return [{"team_name": t.team_name} for t in teams]


@router.get("/leaderboard")
def team_leaderboard(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    t1 = select(
        Match.team1.label("team"),
        case((Match.team1_win == True, 1), else_=0).label("won"),
        Match.match_datetime,
    )
    t2 = select(
        Match.team2.label("team"),
        case((Match.team1_win == False, 1), else_=0).label("won"),
        Match.match_datetime,
    )

    union = union_all(t1, t2).subquery()

    team_stats = (
        db.query(
            union.c.team.label("team_name"),
            func.count().label("total_matches"),
            func.sum(union.c.won).label("wins"),
        )
        .group_by(union.c.team)
        .having(func.count() >= 5)
        .all()
    )

    results = []
    for row in team_stats:
        name = row.team_name
        total = row.total_matches
        wins = int(row.wins)
        results.append({
            "team_name": name,
            "total_matches": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total, 4),
        })

    results.sort(key=lambda x: x["win_rate"], reverse=True)
    top = results[:limit]

    for r in top:
        name = r["team_name"]
        last10 = (
            db.query(union.c.won)
            .filter(union.c.team == name)
            .order_by(desc(union.c.match_datetime))
            .limit(10)
            .all()
        )
        if last10:
            r["recent_10_wr"] = round(sum(row[0] for row in last10) / len(last10), 4)
        else:
            r["recent_10_wr"] = r["win_rate"]

    return top


@router.get("/{team_name}")
def team_profile(team_name: str, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.team_name.ilike(f"%{team_name}%")).first()
    if not team:
        return {"error": "Team not found"}
    result = get_team_features(team.team_name, db)
    if not result:
        return {"error": f"No match data for '{team.team_name}'"}
    return result


@router.get("/{team_name}/lineup")
def team_lineup(team_name: str, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.team_name.ilike(f"%{team_name}%")).first()
    if not team:
        return {"error": "Team not found"}

    from backend.app.services.team_features import _get_current_lineup
    lineup = _get_current_lineup(team.team_name, db)

    return {
        "team_name": team.team_name,
        "lineup": lineup,
    }

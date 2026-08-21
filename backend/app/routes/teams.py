from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.database import get_db
from backend.app.models.models import Team, Match
from backend.app.services.team_features import get_team_features
from backend.app.services.team_hero_features import get_team_hero_pool
from backend.app.utils import match_winner

router = APIRouter()


@router.get("/")
def list_teams(db: Session = Depends(get_db)):
    teams = db.query(Team).all()
    return [{"team_name": t.team_name} for t in teams]


@router.get("/leaderboard")
def team_leaderboard(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    from sqlalchemy import func as sqlfunc, case

    dedup_ids = (
        db.query(sqlfunc.min(Match.id).label("id"))
        .group_by(Match.match_id)
        .subquery()
    )

    t1 = (
        db.query(
            Match.team1.label("team_name"),
            func.count().label("total"),
            func.sum(case((Match.team1_win == True, 1), else_=0)).label("wins"),
        )
        .join(dedup_ids, Match.id == dedup_ids.c.id)
        .filter(Match.team1.isnot(None))
        .group_by(Match.team1)
        .subquery()
    )

    t2 = (
        db.query(
            Match.team2.label("team_name"),
            func.count().label("total"),
            func.sum(case((Match.team1_win == False, 1), else_=0)).label("wins"),
        )
        .join(dedup_ids, Match.id == dedup_ids.c.id)
        .filter(Match.team2.isnot(None))
        .group_by(Match.team2)
        .subquery()
    )

    all_t1 = db.query(t1.c.team_name, t1.c.total, t1.c.wins).all()
    t2_map = {row.team_name: (row.total, row.wins or 0) for row in db.query(t2.c.team_name, t2.c.total, t2.c.wins).all()}

    results = []
    for row in all_t1:
        name = row.team_name
        t1_total = row.total
        t1_wins = row.wins or 0
        t2_total, t2_wins = t2_map.get(name, (0, 0))
        total = t1_total + t2_total
        wins = t1_wins + t2_wins
        if total < 5:
            continue
        results.append({
            "team_name": name,
            "total_matches": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total, 4),
        })

    results.sort(key=lambda x: x["win_rate"], reverse=True)
    top = results[:limit]

    team_names = [r["team_name"] for r in top]
    if team_names:
        recent = (
            db.query(Match)
            .join(dedup_ids, Match.id == dedup_ids.c.id)
            .filter(
                ((Match.team1.in_(team_names)) | (Match.team2.in_(team_names)))
                & (Match.match_datetime.isnot(None))
            )
            .order_by(Match.match_datetime.desc())
            .all()
        )
        recent_by_team = {}
        for m in recent:
            for name in team_names:
                if m.team1 == name or m.team2 == name:
                    if name not in recent_by_team:
                        recent_by_team[name] = []
                    if len(recent_by_team[name]) < 10:
                        if match_winner(m) is None:
                            continue
                        won = (m.team1 == name and m.team1_win) or (m.team2 == name and not m.team1_win)
                        recent_by_team[name].append(won)

        for r in top:
            last10 = recent_by_team.get(r["team_name"], [])
            r["recent_10_wr"] = round(sum(1 for w in last10 if w) / len(last10), 4) if last10 else r["win_rate"]

    return top


@router.get("/{team_name}/heroes")
def team_heroes(team_name: str, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.team_name.ilike(f"%{team_name}%")).first()
    if not team:
        return {"error": "Team not found"}
    return get_team_hero_pool(team.team_name, db)


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

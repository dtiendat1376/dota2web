from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.database import get_db
from backend.app.services.tournament_features import (
    get_tournament_list,
    get_tournament_detail,
    get_tournament_standings,
)

router = APIRouter()


@router.get("/")
def list_tournaments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    from backend.app.models.models import Tournament
    from sqlalchemy import desc

    if search:
        tournaments = (
            db.query(Tournament)
            .filter(Tournament.tournament_name.ilike(f"%{search}%"))
            .order_by(desc(Tournament.tournament_id))
            .offset(offset)
            .limit(limit)
            .all()
        )
        total = (
            db.query(Tournament)
            .filter(Tournament.tournament_name.ilike(f"%{search}%"))
            .count()
        )
    else:
        tournaments = (
            db.query(Tournament)
            .order_by(desc(Tournament.tournament_id))
            .offset(offset)
            .limit(limit)
            .all()
        )
        total = db.query(Tournament).count()

    results = []
    for t in tournaments:
        from backend.app.services.tournament_features import _detect_champion, _infer_tier
        from backend.app.models.models import Match
        from collections import defaultdict

        matches = db.query(Match).filter(Match.tournament_id == t.tournament_id).all()
        if not matches:
            continue

        dates = [m.match_datetime for m in matches if m.match_datetime]
        teams = set()
        for m in matches:
            teams.add(m.team1)
            teams.add(m.team2)

        start_date = min(dates) if dates else None
        end_date = max(dates) if dates else None
        duration = (end_date - start_date).days if start_date and end_date else 0

        final = _detect_champion(t.tournament_id, db)

        results.append(
            {
                "tournament_id": t.tournament_id,
                "tournament_name": t.tournament_name,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "duration": duration,
                "total_matches": len(matches),
                "total_teams": len(teams),
                "tier": _infer_tier(t.tournament_name),
                "champion": final["champion"] if final else None,
                "runner_up": final["runner_up"] if final else None,
            }
        )

    return {"total": total, "tournaments": results}


@router.get("/{tournament_id}")
def tournament_detail(tournament_id: int, db: Session = Depends(get_db)):
    result = get_tournament_detail(tournament_id, db)
    if not result:
        return {"error": "Tournament not found"}
    return result


@router.get("/{tournament_id}/standings")
def tournament_standings(tournament_id: int, db: Session = Depends(get_db)):
    result = get_tournament_standings(tournament_id, db)
    if not result:
        return {"error": "Tournament not found"}
    return result

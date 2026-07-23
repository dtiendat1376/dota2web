from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from collections import defaultdict

from backend.app.database import get_db
from backend.app.models.models import Tournament, Match
from backend.app.services.tournament_features import (
    get_tournament_list,
    get_tournament_detail,
    get_tournament_standings,
    _infer_tier,
)

router = APIRouter()


@router.get("/")
def list_tournaments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
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

        results = []
        tournament_ids = [t.tournament_id for t in tournaments]

        from backend.app.utils import dedup_matches
        all_matches = db.query(Match).filter(Match.tournament_id.in_(tournament_ids)).all()
        matches_by_tid = defaultdict(list)
        for m in all_matches:
            matches_by_tid[m.tournament_id].append(m)

        finals = db.query(Match).filter(
            Match.tournament_id.in_(tournament_ids),
            Match.best_of.in_([3, 5])
        ).order_by(desc(Match.match_datetime)).all()
        finals_by_tid = {}
        for f in finals:
            if f.tournament_id not in finals_by_tid:
                finals_by_tid[f.tournament_id] = f

        for t in tournaments:
            rows = matches_by_tid.get(t.tournament_id, [])
            matches = dedup_matches(rows)
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

            final_match = finals_by_tid.get(t.tournament_id)
            final = None
            if final_match:
                final = {
                    "champion": final_match.team1 if final_match.team1_win else final_match.team2,
                    "runner_up": final_match.team2 if final_match.team1_win else final_match.team1,
                    "score": f"{final_match.score1}-{final_match.score2}",
                    "final_format": f"Bo{final_match.best_of}",
                }

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
    else:
        results = get_tournament_list(db, limit=limit, offset=offset)
        total = db.query(Tournament).count()
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

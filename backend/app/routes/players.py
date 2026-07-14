from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, case, func, select, union_all

from backend.app.database import get_db
from backend.app.models.models import Player, Match
from backend.app.services.player_features import get_player_profile, get_player_team_list

router = APIRouter()


@router.get("/")
def list_players(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str = None,
    min_matches: int = Query(10, ge=0),
    db: Session = Depends(get_db),
):
    if search:
        query = db.query(Player).filter(Player.player_name.ilike(f"%{search}%"))
        total = query.count()
        players = query.offset(offset).limit(limit).all()
    else:
        p1 = select(Match.player1_1.label("pid"))
        p2 = select(Match.player1_2.label("pid"))
        p3 = select(Match.player1_3.label("pid"))
        p4 = select(Match.player1_4.label("pid"))
        p5 = select(Match.player1_5.label("pid"))
        p6 = select(Match.player2_1.label("pid"))
        p7 = select(Match.player2_2.label("pid"))
        p8 = select(Match.player2_3.label("pid"))
        p9 = select(Match.player2_4.label("pid"))
        p10 = select(Match.player2_5.label("pid"))

        from sqlalchemy import union_all as ua
        all_pids = ua(p1, p2, p3, p4, p5, p6, p7, p8, p9, p10).subquery()

        active_pids = (
            db.query(all_pids.c.pid)
            .filter(all_pids.c.pid.isnot(None))
            .group_by(all_pids.c.pid)
            .having(func.count() >= min_matches)
            .subquery()
        )

        query = db.query(Player).filter(Player.player_id.in_(select(active_pids.c.pid)))
        total = query.count()
        players = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "players": [{"player_id": p.player_id, "player_name": p.player_name} for p in players],
    }


@router.get("/{player_id}")
def player_profile(player_id: int, db: Session = Depends(get_db)):
    result = get_player_profile(player_id, db)
    if not result:
        return {"error": "Player not found"}
    return result


@router.get("/{player_id}/teams")
def player_teams(player_id: int, db: Session = Depends(get_db)):
    result = get_player_team_list(player_id, db)
    if result is None:
        return {"error": "Player not found"}
    return {"player_id": player_id, "teams": result}

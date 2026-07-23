from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.services.hero_features import get_hero_list, get_hero_detail, get_hero_matches

router = APIRouter()


@router.get("/")
def list_heroes(
    sort: str = Query("pick_count", pattern="^(pick_count|win_rate|avg_kills|avg_gpm)$"),
    attr: str = Query(None),
    db: Session = Depends(get_db),
):
    return get_hero_list(db, sort_by=sort, attr=attr)


@router.get("/{hero_id}")
def hero_detail(hero_id: int, db: Session = Depends(get_db)):
    result = get_hero_detail(hero_id, db)
    if not result:
        return {"error": "Hero not found"}
    return result


@router.get("/{hero_id}/matches")
def hero_matches(
    hero_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return get_hero_matches(hero_id, db, limit=limit, offset=offset)

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.services.lineup_features import analyze_lineup, find_similar_lineups

router = APIRouter()


class LineupRequest(BaseModel):
    player_ids: List[int]


class SimilarRequest(BaseModel):
    player_ids: List[int]
    limit: int = 10


@router.post("/analyze")
def lineup_analyze(req: LineupRequest, db: Session = Depends(get_db)):
    if len(req.player_ids) != 5:
        return {"error": "Exactly 5 player IDs required"}
    result = analyze_lineup(req.player_ids, db)
    return result


@router.post("/similar")
def lineup_similar(req: SimilarRequest, db: Session = Depends(get_db)):
    if len(req.player_ids) != 5:
        return {"error": "Exactly 5 player IDs required"}
    result = find_similar_lineups(req.player_ids, db, limit=req.limit)
    return result

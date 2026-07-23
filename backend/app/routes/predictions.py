from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.services.prediction import predict_match, get_prediction_history, backtest

router = APIRouter()


class PredictRequest(BaseModel):
    team1: str
    team2: str
    match_id: Optional[int] = None


class BacktestRequest(BaseModel):
    team1: str
    team2: str
    limit: int = 50


@router.post("/predict")
def predict(req: PredictRequest, db: Session = Depends(get_db)):
    result = predict_match(req.team1, req.team2, db, match_id=req.match_id)
    return result


@router.post("/backtest")
def run_backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    return backtest(req.team1, req.team2, db, limit=req.limit)


@router.get("/history")
def prediction_history(db: Session = Depends(get_db)):
    return get_prediction_history(db)

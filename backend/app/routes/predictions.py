from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.services.prediction import predict_match, get_prediction_history

router = APIRouter()


class PredictRequest(BaseModel):
    team1: str
    team2: str


@router.post("/predict")
def predict(req: PredictRequest, db: Session = Depends(get_db)):
    result = predict_match(req.team1, req.team2, db)
    return result


@router.get("/history")
def prediction_history(db: Session = Depends(get_db)):
    return get_prediction_history(db)

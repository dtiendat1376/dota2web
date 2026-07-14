from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.services.h2h_features import get_h2h

router = APIRouter()


class H2HRequest(BaseModel):
    team1: str
    team2: str


@router.post("/")
def h2h_analysis(req: H2HRequest, db: Session = Depends(get_db)):
    result = get_h2h(req.team1, req.team2, db)
    if not result:
        return {"error": "One or both teams not found"}
    return result

from fastapi import APIRouter
from backend.scripts.verify_hero_stats import get_verification_status, run_hero_verification

router = APIRouter()


@router.get("/status")
def verification_status():
    return get_verification_status()


@router.post("/run")
def trigger_verification():
    return run_hero_verification()

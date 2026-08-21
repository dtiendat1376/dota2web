from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional
import json

from backend.app.database import get_db
from backend.app.models.models import Match, Team, Tournament, MatchDetail, MatchPlayerStat, Hero
from backend.app.utils import match_winner

router = APIRouter()


@router.get("/")
def list_matches(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    team: Optional[str] = None,
    db: Session = Depends(get_db),
):
    subq = (
        db.query(
            Match.match_id,
            func.min(Match.id).label("min_rowid"),
        )
        .group_by(Match.match_id)
    )

    if team:
        subq = subq.filter(
            (Match.team1.ilike(f"%{team}%")) | (Match.team2.ilike(f"%{team}%"))
        )

    subq = subq.subquery()

    query = (
        db.query(Match, Tournament.tournament_name)
        .join(subq, Match.id == subq.c.min_rowid)
        .join(Tournament, Match.tournament_id == Tournament.tournament_id, isouter=True)
        .order_by(desc(Match.match_datetime))
    )

    total = db.query(func.count()).select_from(subq).scalar()
    rows = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "matches": [
            {
                "match_id": m.match_id,
                "game_id": m.game_id,
                "tournament": t_name or "Unknown",
                "team1": m.team1,
                "team2": m.team2,
                "score1": m.score1,
                "score2": m.score2,
                "best_of": m.best_of,
                "datetime": m.match_datetime.isoformat() if m.match_datetime else None,
                "team1_win": m.team1_win,
            }
            for m, t_name in rows
        ],
    }


@router.get("/team/{team_name}/stats")
def team_stats(team_name: str, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.team_name.ilike(f"%{team_name}%")).first()
    if not team:
        return {"error": "Team not found"}

    name = team.team_name
    rows = db.query(Match).filter(
        (Match.team1 == name) | (Match.team2 == name)
    ).order_by(desc(Match.match_datetime)).all()
    seen = set()
    matches = []
    for m in rows:
        if m.match_id not in seen:
            seen.add(m.match_id)
            matches.append(m)

    if not matches:
        return {"team": name, "total_matches": 0}

    wins = sum(1 for m in matches if (m.team1 == name and m.team1_win) or (m.team2 == name and not m.team1_win) if match_winner(m) is not None)

    recent_5 = []
    for m in matches[:5]:
        opponent = m.team2 if m.team1 == name else m.team1
        if match_winner(m) is None:
            won = None
        else:
            won = (m.team1 == name and m.team1_win) or (m.team2 == name and not m.team1_win)
        recent_5.append({
            "match_id": m.match_id,
            "opponent": opponent,
            "won": won,
            "score": f"{m.score1}-{m.score2}",
            "datetime": m.match_datetime.isoformat() if m.match_datetime else None,
        })

    decisive = sum(1 for m in matches if match_winner(m) is not None)
    return {
        "team": name,
        "total_matches": len(matches),
        "wins": wins,
        "losses": decisive - wins,
        "draws": len(matches) - decisive,
        "win_rate": round(wins / decisive, 4) if decisive else 0.0,
        "recent_5": recent_5,
    }


@router.get("/{match_id}/detail")
def match_detail(match_id: int, db: Session = Depends(get_db)):
    game = db.query(Match).filter(Match.match_id == match_id).first()
    if not game:
        return {"error": "Match not found"}

    if not game.dota_game_id:
        return {"error": "No game data available for this match"}

    detail = db.query(MatchDetail).filter(MatchDetail.dota_game_id == game.dota_game_id).first()
    if not detail:
        return {"error": "Game data not yet fetched from OpenDota", "dota_game_id": game.dota_game_id}

    stats = (
        db.query(MatchPlayerStat)
        .filter(MatchPlayerStat.dota_game_id == game.dota_game_id)
        .order_by(MatchPlayerStat.player_slot)
        .all()
    )

    hero_ids = set(s.hero_id for s in stats if s.hero_id)
    heroes = db.query(Hero).filter(Hero.hero_id.in_(hero_ids)).all() if hero_ids else []
    hero_map = {h.hero_id: h.localized_name for h in heroes}

    players = []
    for s in stats:
        is_radiant = s.player_slot < 128
        position = s.player_slot if is_radiant else s.player_slot - 128
        players.append({
            "player_slot": s.player_slot,
            "team": "radiant" if is_radiant else "dire",
            "position": position,
            "hero_id": s.hero_id,
            "hero_name": hero_map.get(s.hero_id, f"Hero {s.hero_id}"),
            "kills": s.kills,
            "deaths": s.deaths,
            "assists": s.assists,
            "gold_per_min": s.gold_per_min,
            "xp_per_min": s.xp_per_min,
            "last_hits": s.last_hits,
            "denies": s.denies,
            "hero_damage": s.hero_damage,
            "tower_damage": s.tower_damage,
            "hero_healing": s.hero_healing,
            "net_worth": s.net_worth,
            "level": s.level,
            "win": s.win,
        })

    picks_bans = None
    if detail.picks_bans:
        try:
            picks_bans = json.loads(detail.picks_bans)
        except (json.JSONDecodeError, TypeError):
            pass

    t = db.query(Tournament).filter(Tournament.tournament_id == game.tournament_id).first()

    return {
        "match_id": game.match_id,
        "dota_game_id": game.dota_game_id,
        "tournament": t.tournament_name if t else "Unknown",
        "team1": game.team1,
        "team2": game.team2,
        "duration": detail.duration,
        "radiant_win": detail.radiant_win,
        "radiant_score": detail.radiant_score,
        "dire_score": detail.dire_score,
        "game_mode": detail.game_mode,
        "patch": detail.patch,
        "start_time": detail.start_time,
        "picks_bans": picks_bans,
        "players": players,
        "datetime": game.match_datetime.isoformat() if game.match_datetime else None,
    }


@router.get("/{match_id}")
def get_match(match_id: int, db: Session = Depends(get_db)):
    m = db.query(Match).filter(Match.match_id == match_id).first()
    if not m:
        return {"error": "Match not found"}

    t = db.query(Tournament).filter(Tournament.tournament_id == m.tournament_id).first()

    return {
        "match_id": m.match_id,
        "game_id": m.game_id,
        "dota_game_id": m.dota_game_id,
        "has_game_data": m.has_game_data,
        "tournament": t.tournament_name if t else "Unknown",
        "team1": m.team1,
        "team2": m.team2,
        "score1": m.score1,
        "score2": m.score2,
        "best_of": m.best_of,
        "datetime": m.match_datetime.isoformat() if m.match_datetime else None,
        "team1_win": m.team1_win,
        "games_played": m.games_played,
    }

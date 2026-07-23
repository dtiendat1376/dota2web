from sqlalchemy.orm import Session
from backend.app.models.models import Match, MatchPlayerStat, Hero
from backend.app.utils import dedup_matches


def get_team_hero_pool(team_name: str, db: Session):
    matches = dedup_matches(
        db.query(Match)
        .filter((Match.team1 == team_name) | (Match.team2 == team_name))
        .all()
    )

    game_ids = [m.dota_game_id for m in matches if m.dota_game_id]
    if not game_ids:
        return []

    match_by_game = {m.dota_game_id: m for m in matches}

    heroes = db.query(Hero).all()
    hero_map = {h.hero_id: h for h in heroes}

    stats = (
        db.query(
            MatchPlayerStat.hero_id,
            MatchPlayerStat.dota_game_id,
            MatchPlayerStat.player_slot,
            MatchPlayerStat.win,
        )
        .filter(MatchPlayerStat.dota_game_id.in_(game_ids))
        .all()
    )

    hero_stats = {}
    for s in stats:
        hero_id = s.hero_id
        if not hero_id:
            continue
        m = match_by_game.get(s.dota_game_id)
        if not m:
            continue
        team_won = (m.team1 == team_name and m.team1_win) or (m.team2 == team_name and not m.team1_win)
        if s.win is None or bool(s.win) != team_won:
            continue

        if hero_id not in hero_stats:
            hero_stats[hero_id] = {"picks": 0, "wins": 0}
        hero_stats[hero_id]["picks"] += 1
        if s.win:
            hero_stats[hero_id]["wins"] += 1

    result = []
    for hero_id, s in hero_stats.items():
        hero = hero_map.get(hero_id)
        if not hero:
            continue
        result.append({
            "hero_id": hero_id,
            "name": hero.localized_name,
            "primary_attr": hero.primary_attr,
            "picks": s["picks"],
            "wins": s["wins"],
            "win_rate": round(s["wins"] / s["picks"], 4) if s["picks"] else 0,
        })

    result.sort(key=lambda x: x["picks"], reverse=True)
    return result[:20]

import json
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.models import MatchDetail, MatchPlayerStat, Hero


def get_hero_list(db: Session, sort_by="pick_count", attr=None):
    heroes = db.query(Hero).all()
    hero_map = {h.hero_id: h for h in heroes}

    stats = (
        db.query(
            MatchPlayerStat.hero_id,
            func.count().label("pick_count"),
            func.sum(MatchPlayerStat.win).label("wins"),
            func.avg(MatchPlayerStat.kills).label("avg_kills"),
            func.avg(MatchPlayerStat.deaths).label("avg_deaths"),
            func.avg(MatchPlayerStat.assists).label("avg_assists"),
            func.avg(MatchPlayerStat.gold_per_min).label("avg_gpm"),
            func.avg(MatchPlayerStat.xp_per_min).label("avg_xpm"),
            func.avg(MatchPlayerStat.last_hits).label("avg_lh"),
        )
        .filter(MatchPlayerStat.hero_id.isnot(None))
        .group_by(MatchPlayerStat.hero_id)
        .all()
    )

    result = []
    for s in stats:
        hero = hero_map.get(s.hero_id)
        if not hero:
            continue
        if attr and hero.primary_attr != attr:
            continue
        result.append({
            "hero_id": s.hero_id,
            "name": hero.localized_name,
            "primary_attr": hero.primary_attr,
            "attack_type": hero.attack_type,
            "pick_count": s.pick_count,
            "wins": s.wins or 0,
            "win_rate": round((s.wins or 0) / s.pick_count, 4) if s.pick_count else 0,
            "avg_kills": round(s.avg_kills or 0, 1),
            "avg_deaths": round(s.avg_deaths or 0, 1),
            "avg_assists": round(s.avg_assists or 0, 1),
            "avg_gpm": round(s.avg_gpm or 0),
            "avg_xpm": round(s.avg_xpm or 0),
            "avg_lh": round(s.avg_lh or 0),
        })

    sort_keys = {
        "pick_count": lambda x: x["pick_count"],
        "win_rate": lambda x: x["win_rate"],
        "avg_kills": lambda x: x["avg_kills"],
        "avg_gpm": lambda x: x["avg_gpm"],
    }
    result.sort(key=sort_keys.get(sort_by, sort_keys["pick_count"]), reverse=True)
    return result


def get_hero_detail(hero_id: int, db: Session):
    hero = db.query(Hero).filter(Hero.hero_id == hero_id).first()
    if not hero:
        return None

    stats = (
        db.query(
            func.count().label("pick_count"),
            func.sum(MatchPlayerStat.win).label("wins"),
            func.avg(MatchPlayerStat.kills).label("avg_kills"),
            func.avg(MatchPlayerStat.deaths).label("avg_deaths"),
            func.avg(MatchPlayerStat.assists).label("avg_assists"),
            func.avg(MatchPlayerStat.gold_per_min).label("avg_gpm"),
            func.avg(MatchPlayerStat.xp_per_min).label("avg_xpm"),
            func.avg(MatchPlayerStat.last_hits).label("avg_lh"),
            func.avg(MatchPlayerStat.denies).label("avg_denies"),
            func.avg(MatchPlayerStat.hero_damage).label("avg_dmg"),
            func.avg(MatchPlayerStat.tower_damage).label("avg_tower"),
            func.avg(MatchPlayerStat.hero_healing).label("avg_heal"),
            func.avg(MatchPlayerStat.net_worth).label("avg_nw"),
        )
        .filter(MatchPlayerStat.hero_id == hero_id)
        .first()
    )

    bans = (
        db.query(MatchDetail.picks_bans)
        .filter(MatchDetail.picks_bans.isnot(None))
        .all()
    )
    ban_count = 0
    for row in bans:
        try:
            pb = json.loads(row[0])
            for entry in pb:
                if not entry.get("is_pick") and entry.get("hero_id") == hero_id:
                    ban_count += 1
        except (json.JSONDecodeError, TypeError):
            continue

    if not stats or not stats.pick_count:
        return {
            "hero_id": hero_id,
            "name": hero.localized_name,
            "primary_attr": hero.primary_attr,
            "attack_type": hero.attack_type,
            "pick_count": 0,
            "ban_count": ban_count,
        }

    return {
        "hero_id": hero_id,
        "name": hero.localized_name,
        "primary_attr": hero.primary_attr,
        "attack_type": hero.attack_type,
        "pick_count": stats.pick_count,
        "ban_count": ban_count,
        "wins": stats.wins or 0,
        "win_rate": round((stats.wins or 0) / stats.pick_count, 4),
        "avg_kills": round(stats.avg_kills or 0, 1),
        "avg_deaths": round(stats.avg_deaths or 0, 1),
        "avg_assists": round(stats.avg_assists or 0, 1),
        "avg_gpm": round(stats.avg_gpm or 0),
        "avg_xpm": round(stats.avg_xpm or 0),
        "avg_lh": round(stats.avg_lh or 0),
        "avg_denies": round(stats.avg_denies or 0),
        "avg_dmg": round(stats.avg_dmg or 0),
        "avg_tower": round(stats.avg_tower or 0),
        "avg_heal": round(stats.avg_heal or 0),
        "avg_nw": round(stats.avg_nw or 0),
    }


def get_hero_matches(hero_id: int, db: Session, limit=20, offset=0):
    hero = db.query(Hero).filter(Hero.hero_id == hero_id).first()
    hero_name = hero.localized_name if hero else f"Hero {hero_id}"

    game_ids = (
        db.query(MatchPlayerStat.dota_game_id)
        .filter(MatchPlayerStat.hero_id == hero_id)
        .distinct()
        .limit(limit)
        .offset(offset)
        .all()
    )
    game_ids = [g[0] for g in game_ids]

    if not game_ids:
        return []

    details = (
        db.query(MatchDetail)
        .filter(MatchDetail.dota_game_id.in_(game_ids))
        .all()
    )
    detail_map = {d.dota_game_id: d for d in details}

    matches = (
        db.query(Match)
        .filter(Match.dota_game_id.in_(game_ids))
        .all()
    )
    match_map = {m.dota_game_id: m for m in matches}

    result = []
    for gid in game_ids:
        d = detail_map.get(gid)
        m = match_map.get(gid)
        if not d:
            continue
        result.append({
            "dota_game_id": gid,
            "duration": d.duration,
            "radiant_win": d.radiant_win,
            "radiant_score": d.radiant_score,
            "dire_score": d.dire_score,
            "team1": m.team1 if m else None,
            "team2": m.team2 if m else None,
            "datetime": m.match_datetime.isoformat() if m and m.match_datetime else None,
            "hero_name": hero_name,
        })

    return result

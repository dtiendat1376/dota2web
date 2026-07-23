from datetime import datetime, timezone
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from backend.app.models.models import Match, Player, Tournament, PlayerIdMap
from backend.app.utils import dedup_matches, did_player_win, get_player_match_info, get_player_team
from backend.app.constants import PLAYER_COLS_T1, PLAYER_COLS_T2, POS_NAMES, OPENDOTA_BASE, OPENDOTA_TIMEOUT
import requests
import logging

logger = logging.getLogger("player_features")


def get_player_profile(player_id: int, db: Session):
    player = db.query(Player).filter(Player.player_id == player_id).first()
    if not player:
        return None

    rows = (
        db.query(Match)
        .filter(
            (Match.player1_1 == player_id)
            | (Match.player1_2 == player_id)
            | (Match.player1_3 == player_id)
            | (Match.player1_4 == player_id)
            | (Match.player1_5 == player_id)
            | (Match.player2_1 == player_id)
            | (Match.player2_2 == player_id)
            | (Match.player2_3 == player_id)
            | (Match.player2_4 == player_id)
            | (Match.player2_5 == player_id)
        )
        .order_by(Match.match_datetime)
        .all()
    )
    matches = dedup_matches(rows)

    if not matches:
        return {
            "player_id": player_id,
            "player_name": player.player_name,
            "career_matches": 0,
            "career_wr": 0.5,
            "primary_position": None,
            "current_team": None,
            "recent_5_wr": 0.5,
            "streak": 0,
        }

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    total = len(matches)
    wins = 0
    team_data = defaultdict(
        lambda: {"matches": 0, "wins": 0, "positions": Counter(), "dates": []}
    )

    for m in matches:
        info = get_player_match_info(m, player_id)
        if not info:
            continue
        team, won, pos = info

        if won:
            wins += 1
        td = team_data[team]
        td["matches"] += 1
        if won:
            td["wins"] += 1
        td["positions"][pos] += 1
        if m.match_datetime:
            td["dates"].append(m.match_datetime)

    all_positions = Counter()
    for td in team_data.values():
        all_positions.update(td["positions"])
    primary_position = all_positions.most_common(1)[0][0] if all_positions else None

    current_team = get_player_team(matches[-1], player_id)

    sorted_teams = sorted(
        team_data.items(), key=lambda x: min(x[1]["dates"]) if x[1]["dates"] else datetime.max
    )

    last5 = matches[-5:]
    last10 = matches[-10:]
    last20 = matches[-20:]

    last5_wins = sum(1 for m in last5 if did_player_win(m, player_id))
    last10_wins = sum(1 for m in last10 if did_player_win(m, player_id))
    last20_wins = sum(1 for m in last20 if did_player_win(m, player_id))

    streak = 0
    for m in reversed(matches):
        won = did_player_win(m, player_id)

        if streak == 0:
            streak = 1 if won else -1
        elif (streak > 0 and won) or (streak < 0 and not won):
            streak += 1 if streak > 0 else -1
        else:
            break

    days_since_last = 0
    if matches[-1].match_datetime:
        days_since_last = (now - matches[-1].match_datetime).days

    career_length = 0
    if matches[0].match_datetime:
        career_length = (now - matches[0].match_datetime).days

    recent_90 = [
        m
        for m in matches
        if m.match_datetime and (now - m.match_datetime).days <= 90
    ]

    recent_2024 = [
        m
        for m in matches
        if m.match_datetime and m.match_datetime.year >= 2024
    ]
    recent_2024_wins = sum(1 for m in recent_2024 if did_player_win(m, player_id))

    longest_win = longest_loss = 0
    cur_w = cur_l = 0
    for m in matches:
        won = did_player_win(m, player_id)
        if won:
            cur_w += 1
            cur_l = 0
            longest_win = max(longest_win, cur_w)
        else:
            cur_l += 1
            cur_w = 0
            longest_loss = max(longest_loss, cur_l)

    tournaments_played = set()
    for m in matches:
        tournaments_played.add(m.tournament_id)

    tourn_wins = []
    bo5_matches = [m for m in matches if m.best_of == 5]
    for m in bo5_matches:
        if did_player_win(m, player_id):
            t = db.query(Tournament).filter(Tournament.tournament_id == m.tournament_id).first()
            tourn_wins.append(
                {
                    "tournament_id": m.tournament_id,
                    "tournament_name": t.tournament_name if t else "Unknown",
                    "team": m.team1 if m.team1_win else m.team2,
                    "date": m.match_datetime.isoformat() if m.match_datetime else None,
                }
            )

    team_history = []
    for team_name, info in sorted_teams:
        dates = sorted(info["dates"])
        wr = info["wins"] / info["matches"] if info["matches"] else 0.5
        primary = info["positions"].most_common(1)[0][0] if info["positions"] else None
        team_history.append(
            {
                "team": team_name,
                "matches": info["matches"],
                "wins": info["wins"],
                "losses": info["matches"] - info["wins"],
                "win_rate": round(wr, 4),
                "primary_position": primary,
                "start_date": dates[0].isoformat() if dates else None,
                "end_date": dates[-1].isoformat() if dates else None,
            }
        )

    return {
        "player_id": player_id,
        "player_name": player.player_name,
        "career_matches": total,
        "career_wr": round(wins / total, 4),
        "career_teams": len(team_data),
        "career_tournaments": len(tournaments_played),
        "primary_position": primary_position,
        "current_team": current_team,
        "recent_5_wr": round(last5_wins / len(last5), 4),
        "recent_10_wr": round(last10_wins / len(last10), 4),
        "recent_20_wr": round(last20_wins / len(last20), 4),
        "streak": streak,
        "days_since_last": days_since_last,
        "activity_rate": round(len(recent_90) / 3, 1),
        "career_length": career_length,
        "recent_form": round(recent_2024_wins / len(recent_2024), 4)
        if recent_2024
        else None,
        "tournament_wins": tourn_wins,
        "longest_win_streak": longest_win,
        "longest_loss_streak": longest_loss,
        "team_history": team_history,
    }


def get_player_team_list(player_id: int, db: Session):
    profile = get_player_profile(player_id, db)
    if not profile:
        return None
    return profile["team_history"]


def get_steam32_id(player_name: str, db: Session):
    mapping = db.query(PlayerIdMap).filter(
        PlayerIdMap.player_name == player_name,
        PlayerIdMap.steam32_id.isnot(None)
    ).order_by(PlayerIdMap.confidence.desc()).first()
    if mapping:
        return {
            "steam32_id": mapping.steam32_id,
            "confidence": mapping.confidence,
            "team_name": mapping.team_name,
        }
    return None


def get_player_career(steam32_id: int):
    endpoints = {
        "profile": f"{OPENDOTA_BASE}/api/players/{steam32_id}",
        "wl": f"{OPENDOTA_BASE}/api/players/{steam32_id}/wl",
        "heroes": f"{OPENDOTA_BASE}/api/players/{steam32_id}/heroes",
        "recent": f"{OPENDOTA_BASE}/api/players/{steam32_id}/recentMatches",
    }

    results = {}
    def fetch(name, url):
        try:
            resp = requests.get(url, timeout=OPENDOTA_TIMEOUT)
            resp.raise_for_status()
            return name, resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch {name} for {steam32_id}: {e}")
            return name, None

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(fetch, name, url): name for name, url in endpoints.items()}
        for future in as_completed(futures):
            name, data = future.result()
            results[name] = data

    profile = results.get("profile") or {}
    wl = results.get("wl") or {"win": 0, "lose": 0}
    heroes = (results.get("heroes") or [])[:10]
    recent = (results.get("recent") or [])[:10]

    total = wl.get("win", 0) + wl.get("lose", 0)
    return {
        "steam32_id": steam32_id,
        "profile": profile.get("profile", {}),
        "win": wl.get("win", 0),
        "lose": wl.get("lose", 0),
        "total": total,
        "win_rate": round(wl.get("win", 0) / total, 4) if total > 0 else 0.5,
        "top_heroes": [
            {
                "hero_id": h.get("hero_id"),
                "games": h.get("games", 0),
                "win": h.get("win", 0),
                "win_rate": round(h.get("win", 0) / h.get("games", 1), 4),
            }
            for h in heroes if h.get("games", 0) > 0
        ],
        "recent_matches": [
            {
                "match_id": m.get("match_id"),
                "hero_id": m.get("hero_id"),
                "win": (m.get("player_slot", 0) < 128) == m.get("radiant_win", False),
                "kills": m.get("kills", 0),
                "deaths": m.get("deaths", 0),
                "assists": m.get("assists", 0),
                "duration": m.get("duration", 0),
                "start_time": m.get("start_time"),
            }
            for m in recent
        ],
    }

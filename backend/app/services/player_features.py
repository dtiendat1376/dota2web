from datetime import datetime
from collections import defaultdict, Counter
from sqlalchemy.orm import Session
from backend.app.models.models import Match, Player, Team, Tournament

PLAYER_COLS_T1 = ["player1_1", "player1_2", "player1_3", "player1_4", "player1_5"]
PLAYER_COLS_T2 = ["player2_1", "player2_2", "player2_3", "player2_4", "player2_5"]
POS_NAMES = ["carry", "mid", "offlane", "sup4", "sup5"]


def get_player_profile(player_id: int, db: Session):
    player = db.query(Player).filter(Player.player_id == player_id).first()
    if not player:
        return None

    matches = (
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

    now = datetime.utcnow()
    total = len(matches)
    wins = 0
    team_data = defaultdict(
        lambda: {"matches": 0, "wins": 0, "positions": Counter(), "dates": []}
    )

    for m in matches:
        found = False
        team = pos = None
        won = False

        for i, col in enumerate(PLAYER_COLS_T1):
            if getattr(m, col) == player_id:
                team = m.team1
                won = m.team1_win
                pos = POS_NAMES[i]
                found = True
                break
        if not found:
            for i, col in enumerate(PLAYER_COLS_T2):
                if getattr(m, col) == player_id:
                    team = m.team2
                    won = not m.team1_win
                    pos = POS_NAMES[i]
                    found = True
                    break

        if not found:
            continue

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

    sorted_teams = sorted(
        team_data.items(), key=lambda x: min(x[1]["dates"]) if x[1]["dates"] else datetime.max
    )
    current_team = sorted_teams[-1][0] if sorted_teams else None

    last5 = matches[-5:]
    last10 = matches[-10:]
    last20 = matches[-20:]

    last5_wins = 0
    for m in last5:
        for i, col in enumerate(PLAYER_COLS_T1):
            if getattr(m, col) == player_id and m.team1_win:
                last5_wins += 1
                break
        else:
            for i, col in enumerate(PLAYER_COLS_T2):
                if getattr(m, col) == player_id and not m.team1_win:
                    last5_wins += 1
                    break

    last10_wins = 0
    for m in last10:
        for i, col in enumerate(PLAYER_COLS_T1):
            if getattr(m, col) == player_id and m.team1_win:
                last10_wins += 1
                break
        else:
            for i, col in enumerate(PLAYER_COLS_T2):
                if getattr(m, col) == player_id and not m.team1_win:
                    last10_wins += 1
                    break

    last20_wins = 0
    for m in last20:
        for i, col in enumerate(PLAYER_COLS_T1):
            if getattr(m, col) == player_id and m.team1_win:
                last20_wins += 1
                break
        else:
            for i, col in enumerate(PLAYER_COLS_T2):
                if getattr(m, col) == player_id and not m.team1_win:
                    last20_wins += 1
                    break

    streak = 0
    for m in reversed(matches):
        won = False
        for i, col in enumerate(PLAYER_COLS_T1):
            if getattr(m, col) == player_id:
                won = m.team1_win
                break
        if not won:
            for i, col in enumerate(PLAYER_COLS_T2):
                if getattr(m, col) == player_id:
                    won = not m.team1_win
                    break

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
    recent_2024_wins = 0
    for m in recent_2024:
        for i, col in enumerate(PLAYER_COLS_T1):
            if getattr(m, col) == player_id and m.team1_win:
                recent_2024_wins += 1
                break
        else:
            for i, col in enumerate(PLAYER_COLS_T2):
                if getattr(m, col) == player_id and not m.team1_win:
                    recent_2024_wins += 1
                    break

    longest_win = longest_loss = 0
    cur_w = cur_l = 0
    for m in matches:
        won = False
        for i, col in enumerate(PLAYER_COLS_T1):
            if getattr(m, col) == player_id:
                won = m.team1_win
                break
        if not won:
            for i, col in enumerate(PLAYER_COLS_T2):
                if getattr(m, col) == player_id:
                    won = not m.team1_win
                    break
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
        won = False
        for i, col in enumerate(PLAYER_COLS_T1):
            if getattr(m, col) == player_id:
                won = m.team1_win
                break
        if not won:
            for i, col in enumerate(PLAYER_COLS_T2):
                if getattr(m, col) == player_id:
                    won = not m.team1_win
                    break
        if won:
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

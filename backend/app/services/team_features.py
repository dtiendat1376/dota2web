import math
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
from sqlalchemy.orm import Session
from backend.app.models.models import Match, Player, Team, Tournament
from backend.app.utils import dedup_matches, did_player_win
from backend.app.constants import PLAYER_COLS_T1, PLAYER_COLS_T2, POS_NAMES


def _get_team_matches(team_name: str, db: Session):
    rows = (
        db.query(Match)
        .filter((Match.team1 == team_name) | (Match.team2 == team_name))
        .order_by(Match.match_datetime)
        .all()
    )
    return dedup_matches(rows)


def _is_win(match, team_name: str) -> bool:
    return (match.team1 == team_name and match.team1_win) or (
        match.team2 == team_name and not match.team1_win
    )


def _score_diff(match, team_name: str) -> int:
    if match.team1 == team_name:
        return match.score1 - match.score2
    return match.score2 - match.score1


def _streak(matches, team_name: str):
    s = 0
    for m in reversed(matches):
        won = _is_win(m, team_name)
        if s == 0:
            s = 1 if won else -1
        elif (s > 0 and won) or (s < 0 and not won):
            s += 1 if s > 0 else -1
        else:
            break
    return s


def _longest_streak(matches, team_name: str, win=True):
    best = 0
    cur = 0
    for m in matches:
        won = _is_win(m, team_name)
        if won == win:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _get_current_lineup(team_name: str, db: Session):
    last_match = (
        db.query(Match)
        .filter((Match.team1 == team_name) | (Match.team2 == team_name))
        .order_by(Match.match_datetime.desc())
        .first()
    )
    if not last_match:
        return []

    if last_match.team1 == team_name:
        pcols = PLAYER_COLS_T1
    else:
        pcols = PLAYER_COLS_T2

    lineup = []
    for i, col in enumerate(pcols):
        pid = getattr(last_match, col)
        if pid:
            player = db.query(Player).filter(Player.player_id == pid).first()
            lineup.append(
                {
                    "player_id": pid,
                    "player_name": player.player_name if player else str(pid),
                    "position": POS_NAMES[i],
                }
            )
    return lineup


def _compute_roster_eras(matches, team_name: str):
    eras = []
    current_era_players = None
    era_start = None

    for m in matches:
        if m.team1 == team_name:
            pcols = PLAYER_COLS_T1
        else:
            pcols = PLAYER_COLS_T2

        players = set()
        for col in pcols:
            pid = getattr(m, col)
            if pid:
                players.add(int(pid))

        if not players:
            continue

        frozen = frozenset(players)
        if current_era_players is None:
            current_era_players = frozen
            era_start = m.match_datetime
        elif len(frozen & current_era_players) < 3:
            eras.append(
                {
                    "players": current_era_players,
                    "start": era_start,
                    "end": m.match_datetime,
                }
            )
            current_era_players = frozen
            era_start = m.match_datetime

    if current_era_players:
        eras.append(
            {
                "players": current_era_players,
                "start": era_start,
                "end": matches[-1].match_datetime if matches else era_start,
            }
        )

    return eras


def get_team_features(team_name: str, db: Session):
    matches = _get_team_matches(team_name, db)
    if not matches:
        return None

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    total = len(matches)
    wins = sum(1 for m in matches if _is_win(m, team_name))

    last5 = matches[-5:]
    last10 = matches[-10:]
    last20 = matches[-20:]
    last50 = matches[-50:]

    last5_wins = sum(1 for m in last5 if _is_win(m, team_name))
    last10_wins = sum(1 for m in last10 if _is_win(m, team_name))
    last20_wins = sum(1 for m in last20 if _is_win(m, team_name))
    last50_wins = sum(1 for m in last50 if _is_win(m, team_name))

    score_diffs = [_score_diff(m, team_name) for m in matches]
    recent10_diffs = [_score_diff(m, team_name) for m in last10]

    days_since_last = 0
    if matches[-1].match_datetime:
        days_since_last = (now - matches[-1].match_datetime).days

    days_since_first = 0
    if matches[0].match_datetime:
        days_since_first = (now - matches[0].match_datetime).days

    gaps = []
    for i in range(1, len(matches)):
        if matches[i].match_datetime and matches[i - 1].match_datetime:
            gap = (matches[i].match_datetime - matches[i - 1].match_datetime).days
            gaps.append(gap)

    recent_90 = [m for m in matches if m.match_datetime and (now - m.match_datetime).days <= 90]
    recent_30 = [m for m in matches if m.match_datetime and (now - m.match_datetime).days <= 30]

    lineup = _get_current_lineup(team_name, db)

    eras = _compute_roster_eras(matches, team_name)
    current_era = eras[-1] if eras else None
    roster_days = 0
    roster_win_rate = wins / total if total else 0.5
    if current_era and current_era["start"]:
        roster_days = (now - current_era["start"]).days
        era_matches = [
            m
            for m in matches
            if m.match_datetime and m.match_datetime >= current_era["start"]
        ]
        era_wins = sum(1 for m in era_matches if _is_win(m, team_name))
        roster_win_rate = era_wins / len(era_matches) if era_matches else 0.5

    decay_weight_total = 0
    decay_wins = 0
    for m in matches:
        if m.match_datetime:
            days_old = (now - m.match_datetime).days
            w = math.exp(-0.05 * days_old)
            decay_weight_total += w
            if _is_win(m, team_name):
                decay_wins += w
    roster_decay_wr = decay_wins / decay_weight_total if decay_weight_total else 0.5

    six_months_ago = now - timedelta(days=180)
    roster_changes = sum(
        1 for era in eras
        if era["start"] and era["start"] >= six_months_ago
    )

    bo1_matches = [m for m in matches if m.best_of == 1]
    bo3_matches = [m for m in matches if m.best_of == 3]
    bo5_matches = [m for m in matches if m.best_of == 5]
    series_matches = bo3_matches + bo5_matches

    bo1_wr = (
        sum(1 for m in bo1_matches if _is_win(m, team_name)) / len(bo1_matches)
        if bo1_matches
        else 0.5
    )
    bo3_wr = (
        sum(1 for m in bo3_matches if _is_win(m, team_name)) / len(bo3_matches)
        if bo3_matches
        else 0.5
    )
    bo5_wr = (
        sum(1 for m in bo5_matches if _is_win(m, team_name)) / len(bo5_matches)
        if bo5_matches
        else 0.5
    )
    series_wr = (
        sum(1 for m in series_matches if _is_win(m, team_name)) / len(series_matches)
        if series_matches
        else 0.5
    )

    player_ids_by_slot = defaultdict(lambda: {"matches": 0, "wins": 0})
    for m in matches:
        if m.team1 == team_name:
            pcols = PLAYER_COLS_T1
        else:
            pcols = PLAYER_COLS_T2
        won = _is_win(m, team_name)
        for i, col in enumerate(pcols):
            pid = getattr(m, col)
            if pid:
                slot = player_ids_by_slot[i]
                slot["matches"] += 1
                if won:
                    slot["wins"] += 1

    player_slot_wr = {}
    for i in range(5):
        slot = player_ids_by_slot[i]
        player_slot_wr[POS_NAMES[i]] = (
            round(slot["wins"] / slot["matches"], 4) if slot["matches"] else 0.5
        )

    recent_matches = []
    for m in reversed(matches[-20:]):
        opponent = m.team2 if m.team1 == team_name else m.team1
        won = _is_win(m, team_name)
        score = f"{m.score1}-{m.score2}"
        tournament = None
        if m.tournament_id:
            t = db.query(Tournament).filter(Tournament.tournament_id == m.tournament_id).first()
            tournament = t.tournament_name if t else None
        recent_matches.append({
            "opponent": opponent,
            "won": won,
            "score": score,
            "best_of": m.best_of,
            "date": m.match_datetime.isoformat() if m.match_datetime else None,
            "tournament": tournament,
        })

    return {
        "team_name": team_name,
        "win_rate": round(wins / total, 4),
        "recent_5_wr": round(last5_wins / len(last5), 4),
        "recent_10_wr": round(last10_wins / len(last10), 4),
        "recent_20_wr": round(last20_wins / len(last20), 4),
        "recent_50_wr": round(last50_wins / len(last50), 4),
        "streak": _streak(matches, team_name),
        "longest_win_streak": _longest_streak(matches, team_name, win=True),
        "longest_loss_streak": _longest_streak(matches, team_name, win=False),
        "total_matches": total,
        "wins": wins,
        "losses": total - wins,
        "avg_score_diff": round(sum(score_diffs) / len(score_diffs), 3),
        "recent_10_score_diff": round(
            sum(recent10_diffs) / len(recent10_diffs), 3
        )
        if recent10_diffs
        else 0,
        "roster_win_rate": round(roster_win_rate, 4),
        "roster_decay_wr": round(roster_decay_wr, 4),
        "roster_days": roster_days,
        "roster_changes_6m": roster_changes,
        "bo1_wr": round(bo1_wr, 4),
        "bo3_wr": round(bo3_wr, 4),
        "bo5_wr": round(bo5_wr, 4),
        "bo1_matches": len(bo1_matches),
        "series_length_wr": round(series_wr, 4),
        "days_since_last": days_since_last,
        "match_frequency_90d": len(recent_90),
        "match_frequency_30d": len(recent_30),
        "avg_gap_between_matches": round(sum(gaps) / len(gaps), 1) if gaps else 0,
        "days_since_first": days_since_first,
        "current_lineup": lineup,
        "recent_matches": recent_matches,
        "player_slot_wr": player_slot_wr,
    }

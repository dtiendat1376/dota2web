from sqlalchemy.orm import Session
from backend.app.models.models import Match, Team, Tournament
from backend.app.utils import dedup_matches, match_winner
from backend.app.constants import PLAYER_COLS_T1, PLAYER_COLS_T2


def _get_h2h_matches(team1: str, team2: str, db: Session):
    rows = (
        db.query(Match)
        .filter(
            ((Match.team1 == team1) & (Match.team2 == team2))
            | ((Match.team1 == team2) & (Match.team2 == team1))
        )
        .order_by(Match.match_datetime)
        .all()
    )
    return dedup_matches(rows)


def get_h2h(team1: str, team2: str, db: Session):
    t1 = db.query(Team).filter(Team.team_name.ilike(f"%{team1}%")).first()
    t2 = db.query(Team).filter(Team.team_name.ilike(f"%{team2}%")).first()

    if not t1 or not t2:
        return None

    t1_name = t1.team_name
    t2_name = t2.team_name

    matches = _get_h2h_matches(t1_name, t2_name, db)

    if not matches:
        return {
            "team1": t1_name,
            "team2": t2_name,
            "total_matches": 0,
            "team1_wins": 0,
            "team2_wins": 0,
            "team1_wr": 0.5,
            "team2_wr": 0.5,
            "h2h_score_diff": 0,
            "recent_5": {"total": 0, "team1_wins": 0, "team2_wins": 0},
            "recent_10_wr": 0.5,
            "match_history": [],
        }

    t1_wins = 0
    for m in matches:
        if match_winner(m) is None:
            continue
        if (m.team1 == t1_name and m.team1_win) or (m.team2 == t1_name and not m.team1_win):
            t1_wins += 1
    decisive = sum(1 for m in matches if match_winner(m) is not None)
    t2_wins = decisive - t1_wins

    score_diffs = []
    for m in matches:
        if m.team1 == t1_name:
            score_diffs.append(m.score1 - m.score2)
        else:
            score_diffs.append(m.score2 - m.score1)

    last5 = matches[-5:]
    last5_t1_wins = sum(
        1
        for m in last5
        if match_winner(m) is not None
        and ((m.team1 == t1_name and m.team1_win) or (m.team2 == t1_name and not m.team1_win))
    )
    last5_decisive = sum(1 for m in last5 if match_winner(m) is not None)

    last10 = matches[-10:]
    last10_t1_wins = sum(
        1
        for m in last10
        if match_winner(m) is not None
        and ((m.team1 == t1_name and m.team1_win) or (m.team2 == t1_name and not m.team1_win))
    )
    last10_decisive = sum(1 for m in last10 if match_winner(m) is not None)

    t1_roster = set()
    t2_roster = set()
    for m in matches[:10]:
        if m.team1 == t1_name:
            for col in PLAYER_COLS_T1:
                pid = getattr(m, col)
                if pid:
                    t1_roster.add(int(pid))
        else:
            for col in PLAYER_COLS_T2:
                pid = getattr(m, col)
                if pid:
                    t1_roster.add(int(pid))

        if m.team2 == t2_name:
            for col in PLAYER_COLS_T2:
                pid = getattr(m, col)
                if pid:
                    t2_roster.add(int(pid))
        else:
            for col in PLAYER_COLS_T1:
                pid = getattr(m, col)
                if pid:
                    t2_roster.add(int(pid))

    match_history = []
    for m in reversed(matches[-15:]):
        winner = match_winner(m)
        if m.team1 == t1_name:
            h1, h2, h1s, h2s = m.team1, m.team2, m.score1, m.score2
        else:
            h1, h2, h1s, h2s = m.team2, m.team1, m.score2, m.score1
        t = db.query(Tournament).filter(Tournament.tournament_id == m.tournament_id).first()
        match_history.append(
            {
                "match_id": m.match_id,
                "team1": h1,
                "team2": h2,
                "score": f"{h1s}-{h2s}",
                "winner": winner,
                "best_of": m.best_of,
                "tournament": t.tournament_name if t else "Unknown",
                "date": m.match_datetime.isoformat() if m.match_datetime else None,
            }
        )

    return {
        "team1": t1_name,
        "team2": t2_name,
        "total_matches": len(matches),
        "team1_wins": t1_wins,
        "team2_wins": t2_wins,
        "team1_wr": round(t1_wins / decisive, 4) if decisive else 0.5,
        "team2_wr": round(t2_wins / decisive, 4) if decisive else 0.5,
        "h2h_score_diff": round(sum(score_diffs) / len(score_diffs), 3),
        "last5": {
            "total": len(last5),
            "team1_wins": last5_t1_wins,
            "team2_wins": last5_decisive - last5_t1_wins,
        },
        "recent_10_wr": round(last10_t1_wins / last10_decisive, 4) if last10_decisive else 0.5,
        "roster_overlap": len(t1_roster & t2_roster),
        "match_history": match_history,
    }

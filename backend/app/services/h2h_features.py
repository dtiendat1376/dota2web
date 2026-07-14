from datetime import datetime
from sqlalchemy.orm import Session
from backend.app.models.models import Match, Team, Tournament

PLAYER_COLS_T1 = ["player1_1", "player1_2", "player1_3", "player1_4", "player1_5"]
PLAYER_COLS_T2 = ["player2_1", "player2_2", "player2_3", "player2_4", "player2_5"]


def _get_h2h_matches(team1: str, team2: str, db: Session):
    return (
        db.query(Match)
        .filter(
            ((Match.team1 == team1) & (Match.team2 == team2))
            | ((Match.team1 == team2) & (Match.team2 == team1))
        )
        .order_by(Match.match_datetime)
        .all()
    )


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
            "recent_5": [],
            "recent_10_wr": 0.5,
            "match_history": [],
        }

    t1_wins = 0
    for m in matches:
        if (m.team1 == t1_name and m.team1_win) or (m.team2 == t1_name and not m.team1_win):
            t1_wins += 1
    t2_wins = len(matches) - t1_wins

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
        if (m.team1 == t1_name and m.team1_win)
        or (m.team2 == t1_name and not m.team1_win)
    )

    last10 = matches[-10:]
    last10_t1_wins = sum(
        1
        for m in last10
        if (m.team1 == t1_name and m.team1_win)
        or (m.team2 == t1_name and not m.team1_win)
    )

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
        winner = m.team1 if m.team1_win else m.team2
        t = db.query(Tournament).filter(Tournament.tournament_id == m.tournament_id).first()
        match_history.append(
            {
                "match_id": m.match_id,
                "team1": m.team1,
                "team2": m.team2,
                "score": f"{m.score1}-{m.score2}",
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
        "team1_wr": round(t1_wins / len(matches), 4),
        "team2_wr": round(t2_wins / len(matches), 4),
        "h2h_score_diff": round(sum(score_diffs) / len(score_diffs), 3),
        "last5": {
            "total": len(last5),
            "team1_wins": last5_t1_wins,
            "team2_wins": len(last5) - last5_t1_wins,
        },
        "recent_10_wr": round(last10_t1_wins / len(last10), 4) if last10 else 0.5,
        "roster_overlap": len(t1_roster & t2_roster),
        "match_history": match_history,
    }

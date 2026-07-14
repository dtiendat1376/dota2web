from datetime import datetime
import math
from sqlalchemy.orm import Session
from backend.app.models.models import Match, Team, Tournament
from backend.app.services.team_features import get_team_features
from backend.app.services.h2h_features import get_h2h


def predict_match(team1: str, team2: str, db: Session):
    t1 = db.query(Team).filter(Team.team_name.ilike(f"%{team1}%")).first()
    t2 = db.query(Team).filter(Team.team_name.ilike(f"%{team2}%")).first()

    if not t1:
        return {"error": f"Team '{team1}' not found"}
    if not t2:
        return {"error": f"Team '{team2}' not found"}

    t1_name = t1.team_name
    t2_name = t2.team_name

    t1_features = get_team_features(t1_name, db)
    t2_features = get_team_features(t2_name, db)

    if not t1_features:
        return {"error": f"No match data for '{t1_name}'"}
    if not t2_features:
        return {"error": f"No match data for '{t2_name}'"}

    h2h = get_h2h(t1_name, t2_name, db)
    h2h_wr = h2h["team1_wr"] if h2h and h2h["total_matches"] > 0 else 0.5
    h2h_matches = h2h["total_matches"] if h2h else 0
    h2h_score_diff = h2h["h2h_score_diff"] if h2h else 0

    h2h_weight = min(0.2, h2h_matches * 0.01)

    def _team_score(feat, h2h_wr_val):
        form_score = (
            feat["win_rate"] * 0.20
            + feat["recent_5_wr"] * 0.20
            + feat["recent_10_wr"] * 0.15
            + feat["roster_decay_wr"] * 0.10
        )

        streak_val = feat["streak"]
        if streak_val > 0:
            streak_score = min(streak_val * 0.01, 0.05)
        else:
            streak_score = max(streak_val * 0.01, -0.05)

        format_score = feat["series_length_wr"] * 0.05

        freq_score = 0
        if feat["match_frequency_90d"] > 15:
            freq_score = 0.02
        elif feat["match_frequency_90d"] < 3:
            freq_score = -0.02

        h2h_score = h2h_wr_val * h2h_weight

        score_diff_norm = max(-0.05, min(0.05, feat["avg_score_diff"] * 0.02))

        return form_score + streak_score + format_score + freq_score + h2h_score + score_diff_norm

    t1_score = _team_score(t1_features, h2h_wr)
    t2_score = _team_score(t2_features, 1 - h2h_wr)

    total = t1_score + t2_score
    t1_prob = t1_score / total if total > 0 else 0.5
    t2_prob = t2_score / total if total > 0 else 0.5

    t1_prob = max(0.05, min(0.95, t1_prob))
    t2_prob = 1 - t1_prob

    return {
        "team1": t1_name,
        "team2": t2_name,
        "team1_win_probability": round(t1_prob, 4),
        "team2_win_probability": round(t2_prob, 4),
        "predicted_winner": t1_name if t1_prob > t2_prob else t2_name,
        "confidence": round(abs(t1_prob - 0.5) * 2, 4),
        "features": {
            "team1": {
                "win_rate": t1_features["win_rate"],
                "recent_5_wr": t1_features["recent_5_wr"],
                "recent_10_wr": t1_features["recent_10_wr"],
                "roster_decay_wr": t1_features["roster_decay_wr"],
                "streak": t1_features["streak"],
                "series_length_wr": t1_features["series_length_wr"],
                "avg_score_diff": t1_features["avg_score_diff"],
                "match_frequency_90d": t1_features["match_frequency_90d"],
                "days_since_last": t1_features["days_since_last"],
                "total_matches": t1_features["total_matches"],
            },
            "team2": {
                "win_rate": t2_features["win_rate"],
                "recent_5_wr": t2_features["recent_5_wr"],
                "recent_10_wr": t2_features["recent_10_wr"],
                "roster_decay_wr": t2_features["roster_decay_wr"],
                "streak": t2_features["streak"],
                "series_length_wr": t2_features["series_length_wr"],
                "avg_score_diff": t2_features["avg_score_diff"],
                "match_frequency_90d": t2_features["match_frequency_90d"],
                "days_since_last": t2_features["days_since_last"],
                "total_matches": t2_features["total_matches"],
            },
            "h2h": {
                "total_matches": h2h_matches,
                "team1_wr": h2h_wr,
                "score_diff": h2h_score_diff,
            },
        },
    }


def get_prediction_history(db: Session, limit: int = 20):
    matches = (
        db.query(Match)
        .filter(Match.has_game_data == True)
        .order_by(Match.match_datetime.desc())
        .limit(limit)
        .all()
    )

    results = []
    for m in matches:
        t = db.query(Tournament).filter(Tournament.tournament_id == m.tournament_id).first()
        results.append(
            {
                "match_id": m.match_id,
                "team1": m.team1,
                "team2": m.team2,
                "score": f"{m.score1}-{m.score2}",
                "winner": m.team1 if m.team1_win else m.team2,
                "tournament": t.tournament_name if t else "Unknown",
                "datetime": m.match_datetime.isoformat() if m.match_datetime else None,
            }
        )

    return results

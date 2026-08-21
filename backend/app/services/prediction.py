from datetime import datetime, timezone
import math
from sqlalchemy.orm import Session
from backend.app.models.models import Match, Team, Tournament, Prediction
from backend.app.services.team_features import get_team_features
from backend.app.services.h2h_features import get_h2h
from backend.app.utils import dedup_matches, match_winner


def predict_match(team1: str, team2: str, db: Session, match_id: int = None):
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
    h2h_recent_10_wr = h2h.get("recent_10_wr", 0.5) if h2h else 0.5
    h2h_roster_overlap = h2h.get("roster_overlap", 0) if h2h else 0

    h2h_base_weight = min(0.15, h2h_matches * 0.008)

    def _team_score(feat, h2h_wr_val):
        form_score = (
            feat["win_rate"] * 0.12
            + feat["roster_decay_wr"] * 0.25
        )

        streak_val = feat["streak"]
        if streak_val > 0:
            streak_score = min(streak_val * 0.008, 0.04)
        else:
            streak_score = max(streak_val * 0.008, -0.04)

        format_score = feat["series_length_wr"] * 0.05

        bo3_score = (feat["bo3_wr"] - 0.5) * 0.08

        freq = feat["match_frequency_90d"]
        freq_score = max(-0.03, min(0.03, (freq - 8) * 0.004))

        score_diff_norm = max(-0.05, min(0.05, feat["avg_score_diff"] * 0.02))

        recent_diff = feat.get("recent_10_score_diff", 0)
        recent_diff_score = max(-0.04, min(0.04, recent_diff * 0.03))

        roster_stability = 0
        roster_d = feat.get("roster_days", 0)
        if roster_d > 60:
            roster_stability = min(0.02, (roster_d - 60) * 0.0005)

        inactivity_penalty = 0
        days_idle = feat.get("days_since_last", 0)
        if days_idle > 30:
            inactivity_penalty = max(-0.02, -0.001 * (days_idle - 30))

        h2h_score = h2h_wr_val * h2h_base_weight

        return (form_score + streak_score + format_score + bo3_score
                + freq_score + score_diff_norm + recent_diff_score
                + roster_stability + inactivity_penalty + h2h_score)

    t1_score = _team_score(t1_features, h2h_wr)
    t2_score = _team_score(t2_features, 1 - h2h_wr)

    h2h_diff_score = max(-0.05, min(0.05, h2h_score_diff * 0.04))
    t1_score += h2h_diff_score

    h2h_recent_score = (h2h_recent_10_wr - 0.5) * 0.10
    t1_score += h2h_recent_score

    overlap_penalty = h2h_roster_overlap * 0.01

    diff = t1_score - t2_score
    t1_prob = 1 / (1 + math.exp(-5 * diff))
    t1_prob = max(0.05, min(0.95, t1_prob))
    t2_prob = 1 - t1_prob

    base_confidence = abs(t1_prob - 0.5) * 2
    t1_matches = t1_features["total_matches"]
    t2_matches = t2_features["total_matches"]
    data_factor = min(1.0, min(t1_matches, t2_matches) / 50)
    h2h_factor = 1.0 + min(0.3, h2h_matches * 0.02)
    overlap_factor = max(0.5, 1.0 - overlap_penalty) if overlap_penalty > 0 else 1.0
    confidence = min(1.0, base_confidence * data_factor * h2h_factor * overlap_factor)

    result = {
        "team1": t1_name,
        "team2": t2_name,
        "team1_win_probability": round(t1_prob, 4),
        "team2_win_probability": round(t2_prob, 4),
        "predicted_winner": t1_name if t1_prob > t2_prob else t2_name,
        "confidence": round(confidence, 4),
        "features": {
            "team1": {
                "win_rate": t1_features["win_rate"],
                "roster_decay_wr": t1_features["roster_decay_wr"],
                "streak": t1_features["streak"],
                "series_length_wr": t1_features["series_length_wr"],
                "bo3_wr": t1_features["bo3_wr"],
                "avg_score_diff": t1_features["avg_score_diff"],
                "recent_10_score_diff": t1_features["recent_10_score_diff"],
                "match_frequency_90d": t1_features["match_frequency_90d"],
                "roster_days": t1_features["roster_days"],
                "days_since_last": t1_features["days_since_last"],
                "total_matches": t1_features["total_matches"],
            },
            "team2": {
                "win_rate": t2_features["win_rate"],
                "roster_decay_wr": t2_features["roster_decay_wr"],
                "streak": t2_features["streak"],
                "series_length_wr": t2_features["series_length_wr"],
                "bo3_wr": t2_features["bo3_wr"],
                "avg_score_diff": t2_features["avg_score_diff"],
                "recent_10_score_diff": t2_features["recent_10_score_diff"],
                "match_frequency_90d": t2_features["match_frequency_90d"],
                "roster_days": t2_features["roster_days"],
                "days_since_last": t2_features["days_since_last"],
                "total_matches": t2_features["total_matches"],
            },
            "h2h": {
                "total_matches": h2h_matches,
                "team1_wr": h2h_wr,
                "score_diff": h2h_score_diff,
                "recent_10_wr": h2h_recent_10_wr,
                "roster_overlap": h2h_roster_overlap,
            },
        },
    }

    if match_id:
        match = db.query(Match).filter(Match.match_id == match_id).first()
        if match:
            actual_winner = match_winner(match)
            pred = Prediction(
                match_id=match_id,
                team1_win_prob=t1_prob,
                team2_win_prob=t2_prob,
                predicted_winner=result["predicted_winner"],
                actual_winner=actual_winner,
                model_version="v2.0",
                created_at=datetime.now(timezone.utc),
            )
            db.add(pred)
            try:
                db.commit()
            except Exception:
                db.rollback()
            result["actual_winner"] = actual_winner
            result["correct"] = result["predicted_winner"] == actual_winner

    return result


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
                "winner": match_winner(m),
                "tournament": t.tournament_name if t else "Unknown",
                "datetime": m.match_datetime.isoformat() if m.match_datetime else None,
            }
        )

    return results


def backtest(team1: str, team2: str, db: Session, limit: int = 50):
    t1 = db.query(Team).filter(Team.team_name.ilike(f"%{team1}%")).first()
    t2 = db.query(Team).filter(Team.team_name.ilike(f"%{team2}%")).first()

    if not t1 or not t2:
        return {"error": "Team not found"}

    t1_name = t1.team_name
    t2_name = t2.team_name

    matches = dedup_matches(
        db.query(Match)
        .filter(
            ((Match.team1 == t1_name) & (Match.team2 == t2_name))
            | ((Match.team1 == t2_name) & (Match.team2 == t1_name))
        )
        .order_by(Match.match_datetime.desc())
        .all()
    )[:limit]

    if not matches:
        return {"error": "No matches found between these teams"}

    results = []
    correct = 0
    total_brier = 0

    for m in matches:
        actual_winner = match_winner(m)

        if actual_winner is None:
            continue

        pred = predict_match(t1_name, t2_name, db, match_id=m.match_id)

        if "error" in pred:
            continue

        is_correct = pred["predicted_winner"] == actual_winner
        if is_correct:
            correct += 1

        actual_prob = pred["team1_win_probability"] if actual_winner == t1_name else pred["team2_win_probability"]
        brier = (1 - actual_prob) ** 2
        total_brier += brier

        results.append({
            "match_id": m.match_id,
            "team1": m.team1,
            "team2": m.team2,
            "score": f"{m.score1}-{m.score2}",
            "actual_winner": actual_winner,
            "predicted_winner": pred["predicted_winner"],
            "team1_win_prob": pred["team1_win_probability"],
            "correct": is_correct,
            "brier": round(brier, 4),
            "datetime": m.match_datetime.isoformat() if m.match_datetime else None,
        })

    n = len(results)
    return {
        "team1": t1_name,
        "team2": t2_name,
        "total_matches": n,
        "correct": correct,
        "accuracy": round(correct / n, 4) if n else 0,
        "avg_brier": round(total_brier / n, 4) if n else 0,
        "results": results,
    }

from datetime import datetime
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app.models.models import Match, Player, Team, Tournament

PLAYER_COLS_T1 = ["player1_1", "player1_2", "player1_3", "player1_4", "player1_5"]
PLAYER_COLS_T2 = ["player2_1", "player2_2", "player2_3", "player2_4", "player2_5"]


def _detect_champion(tournament_id: int, db: Session):
    bo5 = (
        db.query(Match)
        .filter(Match.tournament_id == tournament_id, Match.best_of == 5)
        .order_by(desc(Match.match_datetime))
        .first()
    )
    if bo5:
        return {
            "champion": bo5.team1 if bo5.team1_win else bo5.team2,
            "runner_up": bo5.team2 if bo5.team1_win else bo5.team1,
            "score": f"{bo5.score1}-{bo5.score2}",
            "final_format": "Bo5",
        }

    bo3 = (
        db.query(Match)
        .filter(Match.tournament_id == tournament_id, Match.best_of == 3)
        .order_by(desc(Match.match_datetime))
        .first()
    )
    if bo3:
        return {
            "champion": bo3.team1 if bo3.team1_win else bo3.team2,
            "runner_up": bo3.team2 if bo3.team1_win else bo3.team1,
            "score": f"{bo3.score1}-{bo3.score2}",
            "final_format": "Bo3",
        }

    return None


def _infer_tier(tournament_name: str):
    name_lower = tournament_name.lower()
    if "the international" in name_lower or "ti " in name_lower:
        return "Tier 1 - Major"
    if "major" in name_lower:
        return "Tier 1 - Major"
    if "dreamleague season" in name_lower and "division" not in name_lower:
        return "Tier 1 - S-Tier"
    if "esl one" in name_lower:
        return "Tier 1 - S-Tier"
    if "blast slam" in name_lower:
        return "Tier 1 - S-Tier"
    if "pgl" in name_lower and "qualif" not in name_lower:
        return "Tier 1 - Major"
    if "division 1" in name_lower or "div 1" in name_lower:
        return "Tier 2 - Division 1"
    if "division 2" in name_lower or "div 2" in name_lower:
        return "Tier 3 - Division 2"
    if "minor" in name_lower:
        return "Tier 3 - Minor"
    if "qualif" in name_lower:
        return "Tier 4 - Qualifier"
    return "Other"


def get_tournament_list(db: Session, limit: int = 50, offset: int = 0):
    tournaments = (
        db.query(Tournament)
        .order_by(desc(Tournament.tournament_id))
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for t in tournaments:
        matches = (
            db.query(Match).filter(Match.tournament_id == t.tournament_id).all()
        )
        if not matches:
            continue

        match_df_like = list(matches)
        dates = [m.match_datetime for m in match_df_like if m.match_datetime]
        teams = set()
        for m in match_df_like:
            teams.add(m.team1)
            teams.add(m.team2)

        start_date = min(dates) if dates else None
        end_date = max(dates) if dates else None
        duration = (end_date - start_date).days if start_date and end_date else 0

        final = _detect_champion(t.tournament_id, db)

        results.append(
            {
                "tournament_id": t.tournament_id,
                "tournament_name": t.tournament_name,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "duration": duration,
                "total_matches": len(match_df_like),
                "total_teams": len(teams),
                "tier": _infer_tier(t.tournament_name),
                "champion": final["champion"] if final else None,
                "runner_up": final["runner_up"] if final else None,
            }
        )

    return results


def get_tournament_detail(tournament_id: int, db: Session):
    t = db.query(Tournament).filter(Tournament.tournament_id == tournament_id).first()
    if not t:
        return None

    matches = (
        db.query(Match).filter(Match.tournament_id == tournament_id).all()
    )
    if not matches:
        return {
            "tournament_id": tournament_id,
            "tournament_name": t.tournament_name,
            "total_matches": 0,
            "total_teams": 0,
        }

    dates = [m.match_datetime for m in matches if m.match_datetime]
    teams = set()
    for m in matches:
        teams.add(m.team1)
        teams.add(m.team2)

    start_date = min(dates) if dates else None
    end_date = max(dates) if dates else None
    duration = (end_date - start_date).days if start_date and end_date else 0

    bo_counts = defaultdict(int)
    for m in matches:
        bo_counts[m.best_of] = bo_counts.get(m.best_of, 0) + 1

    final = _detect_champion(tournament_id, db)

    return {
        "tournament_id": tournament_id,
        "tournament_name": t.tournament_name,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "duration": duration,
        "total_matches": len(matches),
        "total_teams": len(teams),
        "tier": _infer_tier(t.tournament_name),
        "champion": final["champion"] if final else None,
        "runner_up": final["runner_up"] if final else None,
        "final_score": final["score"] if final else None,
        "final_format": final["final_format"] if final else None,
        "best_of_distribution": dict(bo_counts),
    }


def get_tournament_standings(tournament_id: int, db: Session):
    t = db.query(Tournament).filter(Tournament.tournament_id == tournament_id).first()
    if not t:
        return None

    matches = (
        db.query(Match).filter(Match.tournament_id == tournament_id).all()
    )
    if not matches:
        return {"tournament_id": tournament_id, "group": [], "playoff": []}

    group_matches = [m for m in matches if m.best_of in (1, 2)]
    playoff_matches = [m for m in matches if m.best_of in (3, 5)]

    def _compute_standings(match_list):
        team_stats = defaultdict(lambda: {"matches": 0, "wins": 0})
        for m in match_list:
            team_stats[m.team1]["matches"] += 1
            team_stats[m.team2]["matches"] += 1
            if m.team1_win:
                team_stats[m.team1]["wins"] += 1
            else:
                team_stats[m.team2]["wins"] += 1

        results = []
        for team_name, info in team_stats.items():
            results.append(
                {
                    "team": team_name,
                    "matches": info["matches"],
                    "wins": info["wins"],
                    "losses": info["matches"] - info["wins"],
                    "win_rate": round(info["wins"] / info["matches"], 4)
                    if info["matches"]
                    else 0.5,
                }
            )
        results.sort(key=lambda x: (-x["wins"], -x["win_rate"]))
        return results

    group_standings = _compute_standings(group_matches)
    playoff_standings = _compute_standings(playoff_matches)

    return {
        "tournament_id": tournament_id,
        "tournament_name": t.tournament_name,
        "group": group_standings,
        "playoff": playoff_standings,
    }

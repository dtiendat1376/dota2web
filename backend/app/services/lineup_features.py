from collections import defaultdict, Counter
from sqlalchemy.orm import Session
from backend.app.models.models import Match, Player, Team, Tournament

PLAYER_COLS_T1 = ["player1_1", "player1_2", "player1_3", "player1_4", "player1_5"]
PLAYER_COLS_T2 = ["player2_1", "player2_2", "player2_3", "player2_4", "player2_5"]
POS_NAMES = ["carry", "mid", "offlane", "sup4", "sup5"]


def _get_player_match_ids(player_id: int, db: Session):
    return set(
        row[0]
        for row in db.query(Match.match_id)
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
        .all()
    )


def _get_player_career(player_id: int, db: Session):
    player = db.query(Player).filter(Player.player_id == player_id).first()
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
        .all()
    )
    total = len(matches)
    wins = 0
    for m in matches:
        for col in PLAYER_COLS_T1:
            if getattr(m, col) == player_id and m.team1_win:
                wins += 1
                break
        else:
            for col in PLAYER_COLS_T2:
                if getattr(m, col) == player_id and not m.team1_win:
                    wins += 1
                    break

    return {
        "player_id": player_id,
        "player_name": player.player_name if player else str(player_id),
        "total_matches": total,
        "wins": wins,
        "win_rate": round(wins / total, 4) if total else 0.5,
    }


def analyze_lineup(player_ids: list, db: Session):
    if len(player_ids) != 5:
        return {"error": "Exactly 5 player IDs required"}

    for pid in player_ids:
        if not pid:
            return {"error": "All 5 player IDs must be provided"}

    player_careers = []
    for pid in player_ids:
        career = _get_player_career(pid, db)
        player_careers.append(career)

    position_fit = True
    assigned_positions = set()
    for i, career in enumerate(player_careers):
        pos = POS_NAMES[i]
        if pos in assigned_positions:
            position_fit = False
        assigned_positions.add(pos)

    match_ids_per_player = {}
    for pid in player_ids:
        match_ids_per_player[pid] = _get_player_match_ids(pid, db)

    pair_matrix = []
    for i in range(5):
        row = []
        for j in range(5):
            if i == j:
                row.append({"matches": 0, "player": player_careers[j]["player_name"]})
            else:
                overlap = len(
                    match_ids_per_player[player_ids[i]]
                    & match_ids_per_player[player_ids[j]]
                )
                row.append(
                    {
                        "matches": overlap,
                        "player": player_careers[j]["player_name"],
                    }
                )
        pair_matrix.append(row)

    lineup_key = tuple(sorted(player_ids))
    all_match_ids = set()
    for pid in player_ids:
        all_match_ids |= match_ids_per_player[pid]

    lineup_matches = 0
    lineup_wins = 0
    for mid in all_match_ids:
        match = db.query(Match).filter(Match.match_id == mid).first()
        if not match:
            continue

        t1_pids = set()
        t2_pids = set()
        for col in PLAYER_COLS_T1:
            pid = getattr(match, col)
            if pid:
                t1_pids.add(int(pid))
        for col in PLAYER_COLS_T2:
            pid = getattr(match, col)
            if pid:
                t2_pids.add(int(pid))

        if t1_pids == set(player_ids) or t2_pids == set(player_ids):
            lineup_matches += 1
            if (t1_pids == set(player_ids) and match.team1_win) or (
                t2_pids == set(player_ids) and not match.team1_win
            ):
                lineup_wins += 1

    avg_wr = (
        sum(c["win_rate"] for c in player_careers) / len(player_careers)
        if player_careers
        else 0.5
    )
    total_exp = sum(c["total_matches"] for c in player_careers)

    player_match_counts = {pid: len(ids) for pid, ids in match_ids_per_player.items()}

    similar = []
    all_lineup_keys = set()
    for mid in all_match_ids:
        match = db.query(Match).filter(Match.match_id == mid).first()
        if not match:
            continue
        for pcols in [PLAYER_COLS_T1, PLAYER_COLS_T2]:
            pids = []
            for col in pcols:
                pid = getattr(match, col)
                if pid:
                    pids.append(int(pid))
            if len(pids) == 5:
                all_lineup_keys.add(tuple(sorted(pids)))

    for other_key in all_lineup_keys:
        if other_key == lineup_key:
            continue
        overlap = len(set(other_key) & set(player_ids))
        if overlap >= 3:
            overlap_count = 0
            overlap_wins = 0
            for mid in all_match_ids:
                match = db.query(Match).filter(Match.match_id == mid).first()
                if not match:
                    continue
                for pcols in [PLAYER_COLS_T1, PLAYER_COLS_T2]:
                    pids = []
                    for col in pcols:
                        pid = getattr(match, col)
                        if pid:
                            pids.append(int(pid))
                    if len(pids) == 5 and tuple(sorted(pids)) == other_key:
                        overlap_count += 1
                        t1_pids_set = set()
                        for col in PLAYER_COLS_T1:
                            pid = getattr(match, col)
                            if pid:
                                t1_pids_set.add(int(pid))
                        if (set(pids) == t1_pids_set and match.team1_win) or (
                            set(pids) != t1_pids_set and not match.team1_win
                        ):
                            overlap_wins += 1

            if overlap_count >= 3:
                names = []
                for pid in sorted(other_key):
                    p = db.query(Player).filter(Player.player_id == pid).first()
                    names.append(p.player_name if p else str(pid))
                similar.append(
                    {
                        "player_ids": list(other_key),
                        "player_names": names,
                        "overlap": overlap,
                        "matches": overlap_count,
                        "win_rate": round(overlap_wins / overlap_count, 4)
                        if overlap_count
                        else 0.5,
                    }
                )

    similar.sort(key=lambda x: (-x["overlap"], -x["matches"]))
    similar = similar[:10]

    return {
        "player_cards": [
            {
                "player_id": c["player_id"],
                "player_name": c["player_name"],
                "position": POS_NAMES[i],
                "career_matches": c["total_matches"],
                "career_wr": c["win_rate"],
            }
            for i, c in enumerate(player_careers)
        ],
        "position_fit": position_fit,
        "combined_stats": {
            "avg_wr": round(avg_wr, 4),
            "total_experience": total_exp,
            "total_wins": sum(c["wins"] for c in player_careers),
        },
        "pair_synergy_matrix": pair_matrix,
        "exact_lineup_history": {
            "matches": lineup_matches,
            "wins": lineup_wins,
            "win_rate": round(lineup_wins / lineup_matches, 4)
            if lineup_matches
            else None,
        },
        "similar_lineups": similar,
        "player_match_counts": player_match_counts,
    }


def find_similar_lineups(player_ids: list, db: Session, limit: int = 10):
    result = analyze_lineup(player_ids, db)
    if "error" in result:
        return result
    return {
        "lineup": player_ids,
        "similar_lineups": result["similar_lineups"],
    }

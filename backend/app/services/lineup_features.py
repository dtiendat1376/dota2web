from sqlalchemy.orm import Session
from backend.app.models.models import Match, Player
from backend.app.utils import dedup_matches, did_player_win
from backend.app.constants import PLAYER_COLS_T1, PLAYER_COLS_T2, POS_NAMES


def _get_player_match_ids(player_id: int, db: Session):
    from sqlalchemy import distinct
    return set(
        row[0]
        for row in db.query(distinct(Match.match_id))
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
        .all()
    )
    matches = dedup_matches(rows)
    total = len(matches)
    wins = sum(1 for m in matches if did_player_win(m, player_id))

    return {
        "player_id": player_id,
        "player_name": player.player_name if player else str(player_id),
        "total_matches": total,
        "wins": wins,
        "win_rate": round(wins / total, 4) if total else 0.5,
        "primary_position": None,
    }


def analyze_lineup(player_ids: list, db: Session):
    if len(player_ids) != 5:
        return {"error": "Exactly 5 player IDs required"}

    for pid in player_ids:
        if not pid:
            return {"error": "All 5 player IDs must be provided"}

    player_careers = []
    match_ids_per_player = {}
    for pid in player_ids:
        rows = (
            db.query(Match)
            .filter(
                (Match.player1_1 == pid)
                | (Match.player1_2 == pid)
                | (Match.player1_3 == pid)
                | (Match.player1_4 == pid)
                | (Match.player1_5 == pid)
                | (Match.player2_1 == pid)
                | (Match.player2_2 == pid)
                | (Match.player2_3 == pid)
                | (Match.player2_4 == pid)
                | (Match.player2_5 == pid)
            )
            .all()
        )
        matches = dedup_matches(rows)
        match_ids_per_player[pid] = set(m.match_id for m in matches)
        total = len(matches)
        wins = sum(1 for m in matches if did_player_win(m, pid))
        player = db.query(Player).filter(Player.player_id == pid).first()
        player_careers.append({
            "player_id": pid,
            "player_name": player.player_name if player else str(pid),
            "total_matches": total,
            "wins": wins,
            "win_rate": round(wins / total, 4) if total else 0.5,
            "primary_position": None,
        })

    position_fit = True
    mismatched_positions = []
    for i, career in enumerate(player_careers):
        assigned_pos = POS_NAMES[i]
        if career.get("primary_position") and career["primary_position"] != assigned_pos:
            position_fit = False
            mismatched_positions.append({
                "player": career["player_name"],
                "assigned": assigned_pos,
                "primary": career["primary_position"],
            })

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
    matches_by_id = {}
    if all_match_ids:
        rows = db.query(Match).filter(Match.match_id.in_(all_match_ids)).all()
        for m in rows:
            matches_by_id[m.match_id] = m

    for mid in all_match_ids:
        match = matches_by_id.get(mid)
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
        match = matches_by_id.get(mid)
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

    all_pids_in_keys = set()
    for key in all_lineup_keys:
        all_pids_in_keys.update(key)
    player_name_map = {}
    if all_pids_in_keys:
        for p in db.query(Player).filter(Player.player_id.in_(all_pids_in_keys)).all():
            player_name_map[p.player_id] = p.player_name

    for other_key in all_lineup_keys:
        if other_key == lineup_key:
            continue
        overlap = len(set(other_key) & set(player_ids))
        if overlap >= 3:
            overlap_count = 0
            overlap_wins = 0
            for mid in all_match_ids:
                match = matches_by_id.get(mid)
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
                names = [player_name_map.get(pid, str(pid)) for pid in sorted(other_key)]
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
        "mismatched_positions": mismatched_positions,
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

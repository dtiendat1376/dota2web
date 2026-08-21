from backend.app.constants import PLAYER_COLS_T1, PLAYER_COLS_T2, POS_NAMES


def match_winner(match):
    """Return the winning team name, or None if the series is a draw.

    The dataset sets team1_win arbitrarily for drawn series (e.g. BO2 1-1),
    so the winner is derived from the final scores instead.
    """
    if match.score1 == match.score2:
        return None
    return match.team1 if match.score1 > match.score2 else match.team2


def dedup_matches(matches):
    """Deduplicate match rows by match_id, keeping the first occurrence.

    The dataset has one row per game within a series. match_id is the
    series-level identifier repeated across games. This helper keeps
    one row per series for correct aggregations.
    """
    seen = set()
    result = []
    for m in matches:
        if m.match_id not in seen:
            seen.add(m.match_id)
            result.append(m)
    return result


def did_player_win(match, player_id) -> bool:
    """Return True if the given player won the match."""
    for col in PLAYER_COLS_T1:
        if getattr(match, col) == player_id:
            return bool(match.team1_win)
    for col in PLAYER_COLS_T2:
        if getattr(match, col) == player_id:
            return not match.team1_win
    return False


def get_player_match_info(match, player_id):
    """Return (team_name, won, position) for a player in a match, or None if not found."""
    for i, col in enumerate(PLAYER_COLS_T1):
        if getattr(match, col) == player_id:
            return match.team1, bool(match.team1_win), POS_NAMES[i]
    for i, col in enumerate(PLAYER_COLS_T2):
        if getattr(match, col) == player_id:
            return match.team2, not match.team1_win, POS_NAMES[i]
    return None


def get_player_team(match, player_id):
    """Return the team name a player is on in a match, or None if not found."""
    for col in PLAYER_COLS_T1:
        if getattr(match, col) == player_id:
            return match.team1
    for col in PLAYER_COLS_T2:
        if getattr(match, col) == player_id:
            return match.team2
    return None

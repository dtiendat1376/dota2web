from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base


class Player(Base):
    __tablename__ = "players"

    player_id = Column(Integer, primary_key=True)
    player_name = Column(String(100), nullable=False)


class Team(Base):
    __tablename__ = "teams"

    team_name = Column(String(200), primary_key=True)


class Tournament(Base):
    __tablename__ = "tournaments"

    tournament_id = Column(Integer, primary_key=True)
    tournament_name = Column(String(300), nullable=False)


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.tournament_id"), nullable=False)
    match_id = Column(BigInteger, nullable=False, index=True)
    game_id = Column(BigInteger, nullable=True)
    dota_game_id = Column(BigInteger, nullable=True)
    has_game_data = Column(Boolean, default=False)

    team1 = Column(String(200), ForeignKey("teams.team_name"), nullable=False)
    team2 = Column(String(200), ForeignKey("teams.team_name"), nullable=False)
    score1 = Column(Integer, nullable=False)
    score2 = Column(Integer, nullable=False)
    best_of = Column(Integer, nullable=True)
    match_datetime = Column(DateTime, nullable=False, index=True)
    team1_win = Column(Boolean, nullable=False)
    games_played = Column(Integer, nullable=True)

    team1_rel = relationship("Team", foreign_keys=[team1])
    team2_rel = relationship("Team", foreign_keys=[team2])
    tournament = relationship("Tournament")

    player1_1 = Column(Integer, ForeignKey("players.player_id"), nullable=True)
    player1_2 = Column(Integer, ForeignKey("players.player_id"), nullable=True)
    player1_3 = Column(Integer, ForeignKey("players.player_id"), nullable=True)
    player1_4 = Column(Integer, ForeignKey("players.player_id"), nullable=True)
    player1_5 = Column(Integer, ForeignKey("players.player_id"), nullable=True)
    player2_1 = Column(Integer, ForeignKey("players.player_id"), nullable=True)
    player2_2 = Column(Integer, ForeignKey("players.player_id"), nullable=True)
    player2_3 = Column(Integer, ForeignKey("players.player_id"), nullable=True)
    player2_4 = Column(Integer, ForeignKey("players.player_id"), nullable=True)
    player2_5 = Column(Integer, ForeignKey("players.player_id"), nullable=True)

    __table_args__ = (
        Index("idx_matches_teams", "team1", "team2"),
        Index("idx_matches_datetime", "match_datetime"),
    )


class MatchDetail(Base):
    __tablename__ = "match_details"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dota_game_id = Column(BigInteger, unique=True, nullable=False)
    duration = Column(Integer, nullable=True)
    radiant_win = Column(Boolean, nullable=True)
    radiant_score = Column(Integer, nullable=True)
    dire_score = Column(Integer, nullable=True)
    game_mode = Column(Integer, nullable=True)
    lobby_type = Column(Integer, nullable=True)
    patch = Column(Integer, nullable=True)
    region = Column(Integer, nullable=True)
    start_time = Column(BigInteger, nullable=True)
    picks_bans = Column(String(5000), nullable=True)
    fetched_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_md_game_id", "dota_game_id"),
    )


class MatchPlayerStat(Base):
    __tablename__ = "match_player_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dota_game_id = Column(BigInteger, nullable=False)
    player_slot = Column(Integer, nullable=False)
    hero_id = Column(Integer, nullable=True)
    kills = Column(Integer, nullable=True)
    deaths = Column(Integer, nullable=True)
    assists = Column(Integer, nullable=True)
    gold_per_min = Column(Integer, nullable=True)
    xp_per_min = Column(Integer, nullable=True)
    last_hits = Column(Integer, nullable=True)
    denies = Column(Integer, nullable=True)
    hero_damage = Column(Integer, nullable=True)
    tower_damage = Column(Integer, nullable=True)
    hero_healing = Column(Integer, nullable=True)
    net_worth = Column(Integer, nullable=True)
    level = Column(Integer, nullable=True)
    win = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_mps_game_id", "dota_game_id"),
        Index("idx_mps_hero", "hero_id"),
    )


class Hero(Base):
    __tablename__ = "heroes"

    hero_id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    localized_name = Column(String(100), nullable=False)
    primary_attr = Column(String(10), nullable=True)
    attack_type = Column(String(20), nullable=True)
    roles = Column(String(200), nullable=True)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(BigInteger, ForeignKey("matches.match_id"), nullable=False)
    team1_win_prob = Column(Float, nullable=False)
    team2_win_prob = Column(Float, nullable=False)
    predicted_winner = Column(String(200), nullable=False)
    actual_winner = Column(String(200), nullable=True)
    model_version = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False)

    match = relationship("Match")


class PlayerIdMap(Base):
    __tablename__ = "player_id_map"

    player_name = Column(String(100), primary_key=True)
    team_name = Column(String(200), primary_key=True)
    steam32_id = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    searched_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_pim_steam32", "steam32_id"),
    )


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    check_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    entity_name = Column(String(100), nullable=True)
    expected_value = Column(Float, nullable=True)
    actual_value = Column(Float, nullable=True)
    deviation = Column(Float, nullable=True)
    status = Column(String(10), nullable=False)
    sample_size = Column(Integer, nullable=True)
    checked_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_vr_check_type", "check_type"),
        Index("idx_vr_entity", "entity_id"),
    )

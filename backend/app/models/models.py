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

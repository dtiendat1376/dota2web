import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { getTeams, getLeaderboard, getTeamProfile, getTeamLineup, getTeamHeroes } from '../api';

const POSITIONS = ['carry', 'mid', 'offlane', 'sup4', 'sup5'];
const POS_LABELS = { carry: 'P1 Carry', mid: 'P2 Mid', offlane: 'P3 Offlane', sup4: 'P4 Support', sup5: 'P5 Hard Sup' };

export default function Teams() {
  const { teamName } = useParams();
  const [teams, setTeams] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null);
  const [profile, setProfile] = useState(null);
  const [lineup, setLineup] = useState(null);
  const [heroPool, setHeroPool] = useState(null);
  const [loading, setLoading] = useState(true);
  const [profLoading, setProfLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      getTeams().catch(() => []),
      getLeaderboard(50).catch(() => []),
    ]).then(([t, lb]) => {
      setTeams(t || []);
      setLeaderboard(lb || []);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (teamName && !selected && teams.length > 0) {
      const decoded = decodeURIComponent(teamName);
      const match = teams.find(t => t.team_name === decoded);
      if (match) {
        selectTeam(match.team_name);
      }
    }
  }, [teamName, teams, selected]);

  const filtered = teams.filter(t =>
    !query || t.team_name.toLowerCase().includes(query.toLowerCase())
  );

  const selectTeam = (name) => {
    setSelected(name);
    setProfLoading(true);
    setProfile(null);
    setLineup(null);
    setHeroPool(null);
    Promise.all([
      getTeamProfile(name).catch(() => null),
      getTeamLineup(name).catch(() => null),
      getTeamHeroes(name).catch(() => null),
    ]).then(([prof, lin, heroes]) => {
      setProfile(prof);
      setLineup(lin);
      setHeroPool(heroes);
      setProfLoading(false);
    });
  };

  const goBack = () => {
    setSelected(null);
    setProfile(null);
    setLineup(null);
    setHeroPool(null);
  };

  if (selected) {
    return (
      <div>
        <button className="back-btn" onClick={goBack}>← Back to Teams</button>
        {profLoading ? <div className="loading">Loading profile...</div> : (
          profile && !profile.error ? (
            <div className="team-profile">
              <div className="tp-header">
                <h2>{profile.team_name}</h2>
                <div className="tp-meta">
                  <span>{profile.total_matches} matches</span>
                  <span>{profile.days_since_first} days since first match</span>
                  {profile.roster_days > 0 && <span>Roster together: {profile.roster_days} days</span>}
                </div>
              </div>

              <div className="cs-grid section-gap">
                <div className="cs-item">
                  <span className={`cs-value ${profile.win_rate >= 0.55 ? 'good' : profile.win_rate < 0.45 ? 'warn' : ''}`}>
                    {(profile.win_rate * 100).toFixed(1)}%
                  </span>
                  <span className="cs-label">Win Rate</span>
                </div>
                <div className="cs-item">
                  <span className={`cs-value ${profile.streak > 0 ? 'good' : 'warn'}`}>
                    {profile.streak > 0 ? `W${profile.streak}` : `L${Math.abs(profile.streak)}`}
                  </span>
                  <span className="cs-label">Current Streak</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value">{profile.wins}-{profile.losses}</span>
                  <span className="cs-label">Record</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value">{profile.avg_score_diff > 0 ? '+' : ''}{profile.avg_score_diff}</span>
                  <span className="cs-label">Avg Score Diff</span>
                </div>
              </div>

              <div className="section section-gap">
                <h3>Form</h3>
                <div className="cs-grid">
                  <div className="cs-item">
                    <span className="cs-value">{(profile.recent_5_wr * 100).toFixed(1)}%</span>
                    <span className="cs-label">Last 5</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{(profile.recent_10_wr * 100).toFixed(1)}%</span>
                    <span className="cs-label">Last 10</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{(profile.recent_20_wr * 100).toFixed(1)}%</span>
                    <span className="cs-label">Last 20</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{(profile.recent_50_wr * 100).toFixed(1)}%</span>
                    <span className="cs-label">Last 50</span>
                  </div>
                </div>
              </div>

              <div className="section section-gap">
                <h3>Roster</h3>
                <div className="cs-grid">
                  <div className="cs-item">
                    <span className="cs-value">{(profile.roster_decay_wr * 100).toFixed(1)}%</span>
                    <span className="cs-label">Decay WR</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{(profile.roster_win_rate * 100).toFixed(1)}%</span>
                    <span className="cs-label">Era WR</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{profile.roster_days}d</span>
                    <span className="cs-label">Roster Age</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{profile.roster_changes_6m}</span>
                    <span className="cs-label">Roster Changes</span>
                  </div>
                </div>
              </div>

              <div className="section section-gap">
                <h3>Format Performance</h3>
                <div className="cs-grid">
                  <div className="cs-item">
                    <span className="cs-value">{(profile.bo1_wr * 100).toFixed(1)}%</span>
                    <span className="cs-label">Bo1 WR ({profile.bo1_matches} m)</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{(profile.bo3_wr * 100).toFixed(1)}%</span>
                    <span className="cs-label">Bo3 WR</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{(profile.bo5_wr * 100).toFixed(1)}%</span>
                    <span className="cs-label">Bo5 WR</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{(profile.series_length_wr * 100).toFixed(1)}%</span>
                    <span className="cs-label">Series WR</span>
                  </div>
                </div>
              </div>

              <div className="section section-gap">
                <h3>Activity</h3>
                <div className="cs-grid">
                  <div className="cs-item">
                    <span className="cs-value">{profile.match_frequency_90d}</span>
                    <span className="cs-label">Matches (90d)</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{profile.match_frequency_30d}</span>
                    <span className="cs-label">Matches (30d)</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{profile.avg_gap_between_matches}d</span>
                    <span className="cs-label">Avg Gap</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{profile.days_since_last}d</span>
                    <span className="cs-label">Last Match</span>
                  </div>
                </div>
              </div>

              <div className="section section-gap">
                <h3>Streaks</h3>
                <div className="cs-grid">
                  <div className="cs-item">
                    <span className="cs-value good">{profile.longest_win_streak}</span>
                    <span className="cs-label">Longest Win</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value warn">{profile.longest_loss_streak}</span>
                    <span className="cs-label">Longest Loss</span>
                  </div>
                  <div className="cs-item">
                    <span className="cs-value">{profile.recent_10_score_diff > 0 ? '+' : ''}{profile.recent_10_score_diff}</span>
                    <span className="cs-label">Last 10 Score Diff</span>
                  </div>
                </div>
              </div>

              {lineup && lineup.lineup && lineup.lineup.length > 0 && (
                <div className="section section-gap">
                  <h3>Current Lineup</h3>
                  <div className="lineup-display">
                    {lineup.lineup.map((p, i) => (
                      <div key={i} className="ld-player">
                        <span className="ld-pos">{POS_LABELS[p.position] || p.position}</span>
                        <span className="ld-name">{p.player_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {profile.recent_matches && profile.recent_matches.length > 0 && (
                <div className="section section-gap">
                  <h3>Recent Matches</h3>
                  <table className="data-table">
                    <thead>
                      <tr><th>Date</th><th>Tournament</th><th>Opponent</th><th>Score</th><th>Bo</th><th>Result</th></tr>
                    </thead>
                    <tbody>
                      {profile.recent_matches.map((m, i) => (
                        <tr key={i}>
                          <td className="meta-cell">{m.date ? new Date(m.date).toLocaleDateString() : '—'}</td>
                          <td>{m.tournament || '—'}</td>
                          <td>{m.opponent}</td>
                          <td className="score">{m.score}</td>
                          <td className="muted-text">{m.best_of != null ? `Bo${m.best_of}` : '—'}</td>
                          <td className={m.won ? 'winner' : 'loser'}>{m.won ? 'W' : 'L'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {heroPool && heroPool.length > 0 && (
                <div className="section section-gap">
                  <h3>Hero Pool</h3>
                  <table className="data-table">
                    <thead>
                      <tr><th>Hero</th><th>Attr</th><th>Picks</th><th>Wins</th><th>Win Rate</th></tr>
                    </thead>
                    <tbody>
                      {heroPool.map((h, i) => (
                        <tr key={i}>
                          <td><strong>{h.name}</strong></td>
                          <td><span className={`hero-attr attr-${h.primary_attr}`}>{h.primary_attr?.toUpperCase()}</span></td>
                          <td>{h.picks}</td>
                          <td>{h.wins}</td>
                          <td className={h.win_rate >= 0.52 ? 'winner' : h.win_rate < 0.48 ? 'loser' : ''}>
                            {(h.win_rate * 100).toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {profile.player_slot_wr && Object.keys(profile.player_slot_wr).length > 0 && (
                <div className="section">
                  <h3>Slot Win Rates (All-time)</h3>
                  <div className="cs-grid">
                    {POSITIONS.map(pos => (
                      <div key={pos} className="cs-item">
                        <span className={`cs-value ${(profile.player_slot_wr[pos] || 0.5) >= 0.55 ? 'good' : (profile.player_slot_wr[pos] || 0.5) < 0.45 ? 'warn' : ''}`}>
                          {((profile.player_slot_wr[pos] || 0.5) * 100).toFixed(1)}%
                        </span>
                        <span className="cs-label">{POS_LABELS[pos]}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="error">{profile?.error || 'Failed to load profile'}</div>
          )
        )}
      </div>
    );
  }

  return (
    <div>
      <h2 className="page-title">Teams</h2>
      <p className="page-desc">
        Browse the leaderboard or search for a team to view detailed features, form, and current lineup.
      </p>

      <div className="controls">
        <input
          className="search-input"
          placeholder="Search teams..."
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        <span className="count">{filtered.length} teams</span>
      </div>

      {loading ? <div className="loading">Loading...</div> : (
        <div className="teams-layout">
          {query && (
            <div className="section section-gap">
              <h2>Search Results</h2>
              <table className="data-table">
                <thead>
                  <tr><th>Team</th><th></th></tr>
                </thead>
                <tbody>
                  {filtered.slice(0, 30).map(t => (
                    <tr key={t.team_name}>
                      <td>{t.team_name}</td>
                      <td>
                        <button className="detail-btn" onClick={() => selectTeam(t.team_name)}>Profile</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="section">
            <h2>Leaderboard</h2>
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Team</th>
                  <th>Matches</th>
                  <th>W</th>
                  <th>L</th>
                  <th>WR</th>
                  <th>Recent 10</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.map((t, i) => (
                  <tr key={t.team_name}>
                    <td>{i + 1}</td>
                    <td>{t.team_name}</td>
                    <td>{t.total_matches}</td>
                    <td>{t.wins}</td>
                    <td>{t.losses}</td>
                    <td className={t.win_rate >= 0.55 ? 'winner' : ''}>{(t.win_rate * 100).toFixed(1)}%</td>
                    <td>{(t.recent_10_wr * 100).toFixed(1)}%</td>
                    <td>
                      <button className="detail-btn" onClick={() => selectTeam(t.team_name)}>Profile</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

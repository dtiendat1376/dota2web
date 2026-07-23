import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { searchPlayers, getPlayerProfile, getTeams, searchPlayersByTeam } from '../api';
import api from '../api';

const POS_NAMES = { carry: 'Position 1 — Carry', mid: 'Position 2 — Mid', offlane: 'Position 3 — Offlane', sup4: 'Position 4 — Support', sup5: 'Position 5 — Hard Support' };

export default function Players() {
  const { playerId } = useParams();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [teams, setTeams] = useState([]);
  const [teamSearch, setTeamSearch] = useState('');
  const [steam32, setSteam32] = useState(null);
  const [career, setCareer] = useState(null);
  const [careerLoading, setCareerLoading] = useState(false);

  useEffect(() => {
    getTeams().then(setTeams).catch(() => {});
  }, []);

  useEffect(() => {
    if (playerId && !selected) {
      searchPlayers(playerId, 50).then(data => {
        const p = (data.players || []).find(pl => String(pl.player_id) === String(playerId));
        if (p) {
          selectPlayer(p);
        }
      }).catch(() => {});
    }
  }, [playerId, selected]);

  const doSearch = useCallback((val) => {
    setQuery(val);
    if (val.length < 2) { setResults([]); return; }
    setSearching(true);
    const searchFn = teamSearch
      ? (s, l) => searchPlayersByTeam(teamSearch, s, l)
      : (s, l) => searchPlayers(s, l);
    searchFn(val, 20).then(data => {
      setResults(data.players || []);
      setSearching(false);
    }).catch(() => setSearching(false));
  }, [teamSearch]);

  const selectPlayer = (p) => {
    setSelected(p);
    setLoading(true);
    setResults([]);
    setQuery(p.player_name);
    setError(null);
    setSteam32(null);
    setCareer(null);
    getPlayerProfile(p.player_id).then(data => {
      setProfile(data);
      setLoading(false);
      api.get(`/api/players/${p.player_id}/steam32`).then(r => r.data).then(d => {
        if (d.steam32_id) {
          setSteam32(d);
          setCareerLoading(true);
          api.get(`/api/players/${p.player_id}/career`).then(r => r.data).then(c => {
            if (!c.error) setCareer(c);
            setCareerLoading(false);
          }).catch(() => setCareerLoading(false));
        }
      }).catch(() => {});
    }).catch(() => { setError('Failed to load player profile'); setLoading(false); });
  };

  const goBack = () => {
    setSelected(null);
    setProfile(null);
    setQuery('');
    setResults([]);
    setError(null);
    setSteam32(null);
    setCareer(null);
  };

  if (selected && profile) {
    return (
      <div>
        <button className="back-btn" onClick={goBack}>← Back to Players</button>
        <div className="player-profile">
          <div className="pp-header">
            <div>
              <h2>{profile.player_name}</h2>
              <div className="pp-meta">
                {profile.current_team && <span className="pp-team">{profile.current_team}</span>}
                <span className="pp-id">ID: {profile.player_id}</span>
                {steam32 && (
                  <span className="pp-id">
                    Steam32: {steam32.steam32_id}
                    <a href={`https://www.opendota.com/players/${steam32.steam32_id}`} target="_blank" rel="noopener noreferrer" style={{ marginLeft: 8, color: '#6cf' }}>OpenDota</a>
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="cs-grid section-gap">
            <div className="cs-item">
              <span className="cs-value">{profile.career_matches}</span>
              <span className="cs-label">Career Matches</span>
            </div>
            <div className="cs-item">
              <span className={`cs-value ${profile.career_wr >= 0.55 ? 'good' : profile.career_wr < 0.45 ? 'warn' : ''}`}>
                {(profile.career_wr * 100).toFixed(1)}%
              </span>
              <span className="cs-label">Career Win Rate</span>
            </div>
            <div className="cs-item">
              <span className="cs-value">{profile.career_teams}</span>
              <span className="cs-label">Teams</span>
            </div>
            <div className="cs-item">
              <span className="cs-value">{profile.career_tournaments}</span>
              <span className="cs-label">Tournaments</span>
            </div>
          </div>

          {career && (
            <div className="section section-gap">
              <h3>OpenDota Career</h3>
              <div className="cs-grid">
                <div className="cs-item">
                  <span className="cs-value">{career.total}</span>
                  <span className="cs-label">Total Matches</span>
                </div>
                <div className="cs-item">
                  <span className={`cs-value ${career.win_rate >= 0.55 ? 'good' : career.win_rate < 0.45 ? 'warn' : ''}`}>
                    {(career.win_rate * 100).toFixed(1)}%
                  </span>
                  <span className="cs-label">Win Rate</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value good">{career.win}</span>
                  <span className="cs-label">Wins</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value warn">{career.lose}</span>
                  <span className="cs-label">Losses</span>
                </div>
              </div>
              {career.top_heroes && career.top_heroes.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h4>Top Heroes</h4>
                  <table className="data-table">
                    <thead>
                      <tr><th>Hero ID</th><th>Games</th><th>Wins</th><th>WR</th></tr>
                    </thead>
                    <tbody>
                      {career.top_heroes.map((h, i) => (
                        <tr key={i}>
                          <td>{h.hero_id}</td>
                          <td>{h.games}</td>
                          <td>{h.win}</td>
                          <td className={h.win_rate >= 0.55 ? 'winner' : h.win_rate < 0.45 ? 'loser' : ''}>
                            {(h.win_rate * 100).toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
          {careerLoading && <div className="loading" style={{ margin: '16px 0' }}>Loading OpenDota career...</div>}

          <div className="cs-grid section-gap">
            <div className="cs-item">
              <span className={`cs-value ${profile.streak > 0 ? 'good' : 'warn'}`}>
                {profile.streak > 0 ? `W${profile.streak}` : `L${Math.abs(profile.streak)}`}
              </span>
              <span className="cs-label">Current Streak</span>
            </div>
            <div className="cs-item">
              <span className="cs-value">{(profile.recent_5_wr * 100).toFixed(1)}%</span>
              <span className="cs-label">Last 5 WR</span>
            </div>
            <div className="cs-item">
              <span className="cs-value">{(profile.recent_10_wr * 100).toFixed(1)}%</span>
              <span className="cs-label">Last 10 WR</span>
            </div>
            <div className="cs-item">
              <span className="cs-value">{(profile.recent_20_wr * 100).toFixed(1)}%</span>
              <span className="cs-label">Last 20 WR</span>
            </div>
          </div>

          <div className="cs-grid section-gap">
            <div className="cs-item">
              <span className="cs-value">{profile.longest_win_streak}</span>
              <span className="cs-label">Longest Win Streak</span>
            </div>
            <div className="cs-item">
              <span className="cs-value">{profile.longest_loss_streak}</span>
              <span className="cs-label">Longest Loss Streak</span>
            </div>
            <div className="cs-item">
              <span className="cs-value">{profile.career_length}d</span>
              <span className="cs-label">Career Length</span>
            </div>
            <div className="cs-item">
              <span className="cs-value">{profile.days_since_last}d</span>
              <span className="cs-label">Days Since Last</span>
            </div>
          </div>

          {profile.recent_form !== null && (
            <div className="section section-gap">
              <h3>Recent Form (2024+)</h3>
              <span className={`cs-value ${(profile.recent_form || 0) >= 0.55 ? 'good' : (profile.recent_form || 0) < 0.45 ? 'warn' : ''}`} style={{ fontSize: '1.2rem' }}>
                {((profile.recent_form || 0) * 100).toFixed(1)}%
              </span>
            </div>
          )}

          {(profile.tournament_wins?.length || 0) > 0 && (
            <div className="section section-gap">
              <h3>Tournament Wins (Bo5 Finals)</h3>
              <table className="data-table">
                <thead>
                  <tr><th>Tournament</th><th>Team</th><th>Date</th></tr>
                </thead>
                <tbody>
                  {profile.tournament_wins.map((tw, i) => (
                    <tr key={i}>
                      <td>{tw.tournament_name}</td>
                      <td>{tw.team}</td>
                      <td>{tw.date ? new Date(tw.date).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {(profile.team_history?.length || 0) > 0 && (
            <div className="section">
              <h3>Team History</h3>
              <table className="data-table">
                <thead>
                  <tr><th>Team</th><th>Position</th><th>Matches</th><th>W</th><th>L</th><th>WR</th><th>Period</th></tr>
                </thead>
                <tbody>
                  {profile.team_history.map((th, i) => (
                    <tr key={i}>
                      <td>{th.team}</td>
                      <td>{th.primary_position || '—'}</td>
                      <td>{th.matches}</td>
                      <td>{th.wins}</td>
                      <td>{th.losses}</td>
                      <td className={th.win_rate >= 0.55 ? 'winner' : th.win_rate < 0.45 ? 'loser' : ''}>
                        {(th.win_rate * 100).toFixed(1)}%
                      </td>
                      <td className="meta-cell">
                        {th.start_date ? new Date(th.start_date).toLocaleDateString() : '—'} — {th.end_date ? new Date(th.end_date).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (selected && loading) {
    return (
      <div>
        <button className="back-btn" onClick={goBack}>← Back to Players</button>
        <div className="loading">Loading profile...</div>
      </div>
    );
  }

  if (selected && error) {
    return (
      <div>
        <button className="back-btn" onClick={goBack}>← Back to Players</button>
        <div className="error">{error}</div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="page-title">Players</h2>
      <p className="page-desc">
        Search for any pro player to view career stats, team history, and tournament wins.
      </p>

      <div className="controls">
        <div style={{ position: 'relative', flex: '0 0 350px' }}>
          <input
            className="search-input"
            placeholder="Search player name..."
            value={query}
            onChange={e => doSearch(e.target.value)}
            style={{ width: '100%' }}
          />
          {searching && <span className="slot-searching" style={{ right: 12 }}>Searching...</span>}
          {results.length > 0 && (
            <div className="slot-dropdown" style={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 10 }}>
              {results.map(p => (
                <div key={p.player_id} className="slot-dropdown-item" onMouseDown={() => selectPlayer(p)}>
                  {p.player_name}
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ position: 'relative', flex: '0 0 200px' }}>
          <select
            className="search-input"
            style={{ width: '100%', padding: '10px 16px' }}
            value={teamSearch}
            onChange={e => {
              const val = e.target.value;
              setTeamSearch(val);
              setQuery('');
              setResults([]);
              if (val) {
                setSearching(true);
                searchPlayersByTeam(val, '', 50).then(data => {
                  setResults(data.players || []);
                  setSearching(false);
                }).catch(() => setSearching(false));
              } else {
                setResults([]);
              }
            }}
          >
            <option value="">Filter by team...</option>
            {teams.map(t => <option key={t.team_name} value={t.team_name}>{t.team_name}</option>)}
          </select>
        </div>
      </div>
    </div>
  );
}

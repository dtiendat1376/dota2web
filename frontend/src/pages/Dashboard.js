import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getStats, getLeaderboard, getMatches, getFetchStatus, getDiscoveryStatus, getVerificationStatus } from '../api';

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [recentMatches, setRecentMatches] = useState([]);
  const [fetchStatus, setFetchStatus] = useState(null);
  const [discovery, setDiscovery] = useState(null);
  const [verification, setVerification] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([getStats(), getLeaderboard(10), getMatches({ limit: 10 }), getFetchStatus(), getDiscoveryStatus(), getVerificationStatus()])
      .then(([s, lb, m, fs, ds, vs]) => {
        setStats(s);
        setLeaderboard(lb);
        setRecentMatches(m.matches);
        setFetchStatus(fs);
        setDiscovery(ds);
        setVerification(vs);
        setLoading(false);
      })
      .catch(() => { setError('Failed to load dashboard data'); setLoading(false); });
  }, []);

  if (loading) return <div className="loading">Loading...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="dashboard">
      <h2 className="page-title">Dota 2 Pro Matches Dashboard</h2>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <h3>{stats.total_matches?.toLocaleString()}</h3>
            <p>Matches</p>
          </div>
          <div className="stat-card">
            <h3>{stats.total_teams}</h3>
            <p>Teams</p>
          </div>
          <div className="stat-card">
            <h3>{stats.total_players?.toLocaleString()}</h3>
            <p>Players</p>
          </div>
          <div className="stat-card">
            <h3>{stats.total_tournaments}</h3>
            <p>Tournaments</p>
          </div>
        </div>
      )}

      <div className="quick-links">
        <Link to="/h2h" className="quick-link-card">
          <span className="ql-icon">⚔</span>
          <span className="ql-label">H2H Prediction</span>
        </Link>
        <Link to="/lineup" className="quick-link-card">
          <span className="ql-icon">👥</span>
          <span className="ql-label">Lineup Builder</span>
        </Link>
        <Link to="/heroes" className="quick-link-card">
          <span className="ql-icon">🛡</span>
          <span className="ql-label">Heroes</span>
        </Link>
        <Link to="/tournaments" className="quick-link-card">
          <span className="ql-icon">🏆</span>
          <span className="ql-label">Tournaments</span>
        </Link>
      </div>

      {fetchStatus && (
        <div className="section section-gap">
          <h2>OpenDota Data</h2>
          <div className="fetcher-progress">
            <div className="fetcher-info">
              <span>Matches fetched: <strong>{fetchStatus.fetched_total?.toLocaleString()}</strong> / {(fetchStatus.fetched_total + fetchStatus.pending)?.toLocaleString()}</span>
              <span className="fetcher-pending">{fetchStatus.pending?.toLocaleString()} pending</span>
            </div>
            <div className="progress-bar-bg">
              <div className="progress-bar-fill" style={{ width: `${(fetchStatus.fetched_total + fetchStatus.pending) > 0 ? (fetchStatus.fetched_total / (fetchStatus.fetched_total + fetchStatus.pending) * 100) : 0}%` }} />
            </div>
            <div className="fetcher-meta">
              <span>Fetcher: {fetchStatus.fetcher_calls_today} / {fetchStatus.fetcher_quota} calls today</span>
              <span>Mapper: {fetchStatus.mapper_calls_today} / {fetchStatus.mapper_quota} calls today</span>
              {fetchStatus.last_fetch_at && <span>Last update: {new Date(fetchStatus.last_fetch_at).toLocaleString()}</span>}
            </div>
          </div>
        </div>
      )}

      {discovery && (
        <div className="section section-gap">
          <h2>OpenDota Discovery</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <h3>{discovery.pro_players_in_db?.toLocaleString()}</h3>
              <p>Pro Players</p>
            </div>
            <div className="stat-card">
              <h3>{discovery.teams_in_db?.toLocaleString()}</h3>
              <p>Teams Indexed</p>
            </div>
            <div className="stat-card">
              <h3>{discovery.team_matches_in_db?.toLocaleString()}</h3>
              <p>Team Matches</p>
            </div>
            <div className="stat-card">
              <h3>{discovery.mapped_players?.toLocaleString()}</h3>
              <p>Players Mapped</p>
            </div>
          </div>
          <div className="fetcher-meta" style={{ marginTop: '0.5rem' }}>
            <span>dota_game_id coverage: {discovery.dota_game_ids?.toLocaleString()} / {discovery.total_matches?.toLocaleString()}</span>
            {discovery.last_run && <span>Last discovery: {new Date(discovery.last_run).toLocaleString()}</span>}
          </div>
        </div>
      )}

      {verification && verification.total > 0 && (
        <div className="section section-gap">
          <h2>Data Verification</h2>
          <div className="verification-summary">
            <span>Checked: {new Date(verification.last_checked).toLocaleString()}</span>
            <div className="verification-counts">
              <span className="vr-pass">{verification.pass} passed</span>
              <span className="vr-warn">{verification.warn} warnings</span>
              <span className="vr-fail">{verification.fail} failures</span>
            </div>
          </div>
          {verification.heroes?.some(h => h.status !== 'pass') && (
            <table className="data-table">
              <thead><tr><th>Hero</th><th>Local WR</th><th>Pro WR</th><th>Deviation</th><th>Samples</th><th>Status</th></tr></thead>
              <tbody>
                {verification.heroes.filter(h => h.status !== 'pass').map(h => (
                  <tr key={h.hero_id} className={h.status === 'fail' ? 'vr-row-fail' : 'vr-row-warn'}>
                    <td><strong>{h.hero_name}</strong></td>
                    <td>{(h.actual_value * 100).toFixed(1)}%</td>
                    <td>{(h.expected_value * 100).toFixed(1)}%</td>
                    <td>{(h.deviation * 100).toFixed(1)}%</td>
                    <td>{h.sample_size}</td>
                    <td className={h.status === 'fail' ? 'vr-fail-text' : 'vr-warn-text'}>{h.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <div className="dashboard-grid">
        <div className="section">
          <h2>Top Teams</h2>
          {leaderboard.length === 0 ? (
            <div className="empty-state">No leaderboard data</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th><th>Team</th><th>W-L</th><th>Win Rate</th><th>Last 10</th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.map((t, i) => (
                  <tr key={t.team_name}>
                    <td>{i + 1}</td>
                    <td><strong>{t.team_name}</strong></td>
                    <td>{t.wins}-{t.losses}</td>
                    <td>{(t.win_rate * 100).toFixed(1)}%</td>
                    <td>{(t.recent_10_wr * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="section">
          <h2>Recent Matches</h2>
          {recentMatches.length === 0 ? (
            <div className="empty-state">No recent matches</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Team 1</th><th>Score</th><th>Team 2</th><th>Date</th>
                </tr>
              </thead>
              <tbody>
                {recentMatches.map((m, i) => {
                  const isDraw = m.score1 === m.score2;
                  return (
                    <tr key={i}>
                      <td className={!isDraw && m.team1_win ? 'winner' : ''}>{m.team1}</td>
                      <td>
                        <strong>{m.score1} - {m.score2}</strong>
                        {isDraw && <span className="draw-badge">Draw</span>}
                      </td>
                      <td className={!isDraw && !m.team1_win ? 'winner' : ''}>{m.team2}</td>
                      <td>{m.datetime ? new Date(m.datetime).toLocaleDateString() : ''}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;

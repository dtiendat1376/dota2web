import React, { useState, useEffect } from 'react';
import { getStats, getLeaderboard, getMatches } from '../api';

function Dashboard() {
  const [stats, setStats] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [recentMatches, setRecentMatches] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getStats(), getLeaderboard(10), getMatches({ limit: 10 })])
      .then(([s, lb, m]) => {
        setStats(s);
        setLeaderboard(lb);
        setRecentMatches(m.matches);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Loading...</div>;

  return (
    <div className="dashboard">
      <h1>Dota 2 Pro Matches Dashboard</h1>

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

      <div className="dashboard-grid">
        <div className="section">
          <h2>Top Teams</h2>
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
        </div>

        <div className="section">
          <h2>Recent Matches</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Team 1</th><th>Score</th><th>Team 2</th><th>Date</th>
              </tr>
            </thead>
            <tbody>
              {recentMatches.map((m, i) => (
                <tr key={i}>
                  <td className={m.team1_win ? 'winner' : ''}>{m.team1}</td>
                  <td><strong>{m.score1} - {m.score2}</strong></td>
                  <td className={!m.team1_win ? 'winner' : ''}>{m.team2}</td>
                  <td>{m.datetime ? new Date(m.datetime).toLocaleDateString() : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;

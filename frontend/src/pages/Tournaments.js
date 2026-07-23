import React, { useState, useEffect } from 'react';
import { getTournaments, getTournamentDetail, getTournamentStandings } from '../api';

export default function Tournaments() {
  const [tournaments, setTournaments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [standings, setStandings] = useState(null);
  const [page, setPage] = useState(0);
  const pageSize = 30;

  useEffect(() => {
    setLoading(true);
    setError(null);
    getTournaments().then(data => {
      setTournaments(data.tournaments || []);
      setLoading(false);
    }).catch(() => { setError('Failed to load tournaments'); setLoading(false); });
  }, []);

  const filtered = tournaments.filter(t =>
    !search || t.tournament_name.toLowerCase().includes(search.toLowerCase())
  );

  const paged = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const totalPages = Math.ceil(filtered.length / pageSize);

  const selectTournament = (t) => {
    setSelected(t);
    setStandings(null);
    getTournamentDetail(t.tournament_id).then(d => setSelected(d)).catch(() => {});
    getTournamentStandings(t.tournament_id).then(d => setStandings(d)).catch(() => {});
  };

  const renderStandingsTable = (teams, title) => (
    <div className="standings-group">
      <h4>{title}</h4>
      <table className="data-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Team</th>
            <th>W</th>
            <th>L</th>
            <th>WR</th>
          </tr>
        </thead>
        <tbody>
          {teams.map((t, ti) => (
            <tr key={ti}>
              <td>{ti + 1}</td>
              <td>{t.team}</td>
              <td>{t.wins}</td>
              <td>{t.losses}</td>
              <td>{(t.win_rate * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  if (selected) {
    return (
      <div>
        <button className="back-btn" onClick={() => { setSelected(null); setStandings(null); }}>
          ← Back to Tournaments
        </button>
        <div className="tournament-detail">
          <div className="tournament-header">
            <div>
              <h2>{selected.tournament_name}</h2>
              <div className="tournament-meta">
                <span className="tier-badge" data-tier={selected.tier}>{selected.tier}</span>
                <span>{selected.start_date} — {selected.end_date}</span>
                <span>{selected.total_matches} matches · {selected.total_teams} teams</span>
              </div>
            </div>
            {selected.champion && (
              <div className="champion-box">
                <div className="champion-label">Champion</div>
                <div className="champion-name">{selected.champion}</div>
                {selected.final_score && <div className="final-score">{selected.final_score}</div>}
              </div>
            )}
          </div>

          <div className="format-summary">
            <h3>Format Breakdown</h3>
            <div className="format-bars">
              {Object.entries(selected.best_of_distribution || {}).map(([fmt, count]) => (
                <div key={fmt} className="format-item">
                  <span className="format-label">Bo{fmt}</span>
                  <span className="format-count">{count}</span>
                </div>
              ))}
            </div>
          </div>

          {standings && (
            <div className="standings-section">
              <h3>Standings</h3>
              {standings.group && standings.group.length > 0 && renderStandingsTable(standings.group, 'Group Stage')}
              {standings.playoff && standings.playoff.length > 0 && renderStandingsTable(standings.playoff, 'Playoffs')}
              {(!standings.group || standings.group.length === 0) && (!standings.playoff || standings.playoff.length === 0) && (
                <p style={{ color: '#888', fontSize: '0.9rem' }}>No standings available for this tournament.</p>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="page-title">Tournaments</h2>
      <div className="controls">
        <input
          className="search-input"
          placeholder="Search tournaments..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(0); }}
        />
        <span className="count">{filtered.length} tournaments</span>
      </div>

      {error && <div className="error">{error}</div>}

      {loading ? <div className="loading">Loading tournaments...</div> : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Tournament</th>
                <th>Tier</th>
                <th>Dates</th>
                <th>Matches</th>
                <th>Champion</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {paged.map(t => (
                <tr key={t.tournament_id}>
                  <td>{t.tournament_name}</td>
                  <td><span className="tier-badge" data-tier={t.tier}>{t.tier}</span></td>
                  <td>{t.start_date} — {t.end_date}</td>
                  <td>{t.total_matches}</td>
                  <td className="winner">{t.champion || '—'}</td>
                  <td>
                    <button className="detail-btn" onClick={() => selectTournament(t)}>
                      Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {totalPages > 1 && (
            <div className="pagination">
              <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
              <span>Page {page + 1} / {totalPages}</span>
              <button disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

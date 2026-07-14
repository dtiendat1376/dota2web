import React, { useState, useEffect } from 'react';
import { getTournaments, getTournamentDetail, getTournamentStandings } from '../api';

export default function Tournaments() {
  const [tournaments, setTournaments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [standings, setStandings] = useState(null);
  const [page, setPage] = useState(0);
  const pageSize = 30;

  useEffect(() => {
    setLoading(true);
    getTournaments().then(data => {
      setTournaments(data.tournaments || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const filtered = tournaments.filter(t =>
    !search || t.name.toLowerCase().includes(search.toLowerCase())
  );

  const paged = filtered.slice(page * pageSize, (page + 1) * pageSize);
  const totalPages = Math.ceil(filtered.length / pageSize);

  const selectTournament = (t) => {
    setSelected(t);
    setStandings(null);
    getTournamentDetail(t.id).then(d => setSelected(d)).catch(() => {});
    getTournamentStandings(t.id).then(d => setStandings(d)).catch(() => {});
  };

  if (selected) {
    return (
      <div>
        <button className="back-btn" onClick={() => { setSelected(null); setStandings(null); }}>
          ← Back to Tournaments
        </button>
        <div className="tournament-detail">
          <div className="tournament-header">
            <div>
              <h2>{selected.name}</h2>
              <div className="tournament-meta">
                <span className="tier-badge" data-tier={selected.tier}>{selected.tier}</span>
                <span>{selected.start_date} — {selected.end_date}</span>
                <span>{selected.num_matches} matches · {selected.num_games} games</span>
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
              {Object.entries(selected.format_summary || {}).map(([fmt, count]) => (
                <div key={fmt} className="format-item">
                  <span className="format-label">{fmt}</span>
                  <span className="format-count">{count}</span>
                </div>
              ))}
            </div>
          </div>

          {standings && standings.standings && standings.standings.length > 0 && (
            <div className="standings-section">
              <h3>Standings</h3>
              {standings.standings.map((group, gi) => (
                <div key={gi} className="standings-group">
                  <h4>{group.group_name || 'Overall'}</h4>
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
                      {group.teams.map((t, ti) => (
                        <tr key={ti}>
                          <td>{ti + 1}</td>
                          <td>{t.team}</td>
                          <td>{t.wins}</td>
                          <td>{t.losses}</td>
                          <td>{t.winrate}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Tournaments</h2>
      <div className="controls">
        <input
          className="search-input"
          placeholder="Search tournaments..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(0); }}
        />
        <span className="count">{filtered.length} tournaments</span>
      </div>

      {loading ? <div className="loading">Loading...</div> : (
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
                <tr key={t.id}>
                  <td>{t.name}</td>
                  <td><span className="tier-badge" data-tier={t.tier}>{t.tier}</span></td>
                  <td>{t.start_date} — {t.end_date}</td>
                  <td>{t.num_matches}</td>
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

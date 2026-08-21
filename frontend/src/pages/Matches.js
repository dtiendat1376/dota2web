import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getMatches } from '../api';

function Matches() {
  const navigate = useNavigate();
  const [matches, setMatches] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const limit = 50;
  const debounceRef = useRef(null);

  const onSearchChange = useCallback((val) => {
    setSearch(val);
    setPage(0);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(val), 300);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getMatches({ limit, offset: page * limit, team: debouncedSearch || undefined })
      .then(data => { setMatches(data.matches); setTotal(data.total); setLoading(false); })
      .catch(() => { setError('Failed to load matches'); setLoading(false); });
  }, [page, debouncedSearch]);

  return (
    <div className="page">
      <h2 className="page-title">Matches</h2>
      <div className="controls">
        <input
          type="text"
          placeholder="Search by team name..."
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          className="search-input"
        />
        <span className="count">{total.toLocaleString()} matches found</span>
      </div>

      {loading && <div className="loading">Loading matches...</div>}
      {error && <div className="error">{error}</div>}

      {!loading && !error && matches.length === 0 && (
        <div className="empty-state">No matches found</div>
      )}

      {!loading && !error && matches.length > 0 && (
        <>
          <table className="data-table full-width">
            <thead>
              <tr>
                <th>Tournament</th><th>Team 1</th><th>Score</th><th>Team 2</th>
                <th>Bo</th><th>Winner</th><th>Date</th><th></th>
              </tr>
            </thead>
            <tbody>
              {matches.map((m, i) => {
                const isDraw = m.score1 === m.score2;
                return (
                  <tr key={i}>
                    <td className="tournament">{m.tournament}</td>
                    <td className={!isDraw && m.team1_win ? 'winner' : ''}><strong>{m.team1}</strong></td>
                    <td className="score">
                      {m.score1} - {m.score2}
                      {isDraw && <span className="draw-badge">Draw</span>}
                    </td>
                    <td className={!isDraw && !m.team1_win ? 'winner' : ''}><strong>{m.team2}</strong></td>
                    <td>{m.best_of != null ? `Bo${m.best_of}` : '—'}</td>
                    <td>{isDraw ? 'Draw' : (m.team1_win ? m.team1 : m.team2)}</td>
                    <td>{m.datetime ? new Date(m.datetime).toLocaleDateString() : ''}</td>
                    <td>
                      <button className="detail-btn" onClick={() => navigate(`/matches/${m.match_id}`)}>
                        Detail
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="pagination">
            <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>Previous</button>
            <span>Page {page + 1} of {Math.ceil(total / limit)}</span>
            <button disabled={(page + 1) * limit >= total} onClick={() => setPage(p => p + 1)}>Next</button>
          </div>
        </>
      )}
    </div>
  );
}

export default Matches;

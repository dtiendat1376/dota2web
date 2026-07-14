import React, { useState, useEffect } from 'react';
import { getMatches } from '../api';

function Matches() {
  const [matches, setMatches] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const limit = 50;

  useEffect(() => {
    getMatches({ limit, offset: page * limit, team: search || undefined })
      .then(data => { setMatches(data.matches); setTotal(data.total); });
  }, [page, search]);

  return (
    <div className="page">
      <h1>Matches</h1>
      <div className="controls">
        <input
          type="text"
          placeholder="Search by team name..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(0); }}
          className="search-input"
        />
        <span className="count">{total.toLocaleString()} matches found</span>
      </div>

      <table className="data-table full-width">
        <thead>
          <tr>
            <th>Tournament</th><th>Team 1</th><th>Score</th><th>Team 2</th>
            <th>Bo</th><th>Winner</th><th>Date</th>
          </tr>
        </thead>
        <tbody>
          {matches.map((m, i) => (
            <tr key={i}>
              <td className="tournament">{m.tournament}</td>
              <td className={m.team1_win ? 'winner' : ''}><strong>{m.team1}</strong></td>
              <td className="score">{m.score1} - {m.score2}</td>
              <td className={!m.team1_win ? 'winner' : ''}><strong>{m.team2}</strong></td>
              <td>Bo{m.best_of}</td>
              <td>{m.team1_win ? m.team1 : m.team2}</td>
              <td>{m.datetime ? new Date(m.datetime).toLocaleDateString() : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="pagination">
        <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>Previous</button>
        <span>Page {page + 1} of {Math.ceil(total / limit)}</span>
        <button disabled={(page + 1) * limit >= total} onClick={() => setPage(p => p + 1)}>Next</button>
      </div>
    </div>
  );
}

export default Matches;

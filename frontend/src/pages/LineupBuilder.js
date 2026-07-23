import React, { useState, useCallback } from 'react';
import { searchPlayers, analyzeLineup } from '../api';

const POSITIONS = [
  { key: 'carry', label: 'Position 1 — Carry', abbr: 'P1' },
  { key: 'mid', label: 'Position 2 — Mid', abbr: 'P2' },
  { key: 'offlane', label: 'Position 3 — Offlane', abbr: 'P3' },
  { key: 'sup4', label: 'Position 4 — Support', abbr: 'P4' },
  { key: 'sup5', label: 'Position 5 — Hard Support', abbr: 'P5' },
];

function PlayerSlot({ position, selected, onSelect, onClear, takenIds }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [showDrop, setShowDrop] = useState(false);
  const [searching, setSearching] = useState(false);

  const doSearch = useCallback((val) => {
    setQuery(val);
    if (val.length < 2) { setResults([]); return; }
    setSearching(true);
    searchPlayers(val, 8).then(data => {
      setResults(data.players || []);
      setShowDrop(true);
      setSearching(false);
    }).catch(() => setSearching(false));
  }, []);

  const pick = (p) => {
    if (takenIds.includes(p.player_id)) return;
    onSelect(p);
    setQuery(p.player_name);
    setShowDrop(false);
  };

  return (
    <div className="lineup-slot">
      <div className="slot-header">
        <span className="slot-position">{position.abbr}</span>
        <span className="slot-label">{position.label}</span>
        {selected && (
          <button className="slot-clear" onClick={() => { onClear(); setQuery(''); setResults([]); }}>×</button>
        )}
      </div>
      <div className="slot-search-wrap">
        <input
          className="slot-search"
          placeholder={`Search ${position.label.toLowerCase()}...`}
          value={query}
          onChange={e => doSearch(e.target.value)}
          onFocus={() => results.length > 0 && setShowDrop(true)}
          onBlur={() => setTimeout(() => setShowDrop(false), 200)}
        />
        {showDrop && results.length > 0 && (
          <div className="slot-dropdown">
            {results.map(p => {
              const taken = takenIds.includes(p.player_id);
              return (
                <div
                  key={p.player_id}
                  className={`slot-dropdown-item ${taken ? 'taken' : ''}`}
                  onMouseDown={() => !taken && pick(p)}
                  style={taken ? { opacity: 0.4, cursor: 'not-allowed' } : {}}
                >
                  {p.player_name} {taken ? '(already selected)' : ''}
                </div>
              );
            })}
          </div>
        )}
        {searching && <span className="slot-searching">Searching...</span>}
      </div>
    </div>
  );
}

function SynergyMatrix({ matrix, players }) {
  if (!matrix || matrix.length === 0) return null;
  const maxMatches = Math.max(...matrix.flat().map(c => c.matches || 0), 1);

  return (
    <div className="synergy-matrix-wrap">
      <table className="synergy-matrix">
        <thead>
          <tr>
            <th></th>
            {players.map((p, i) => (
              <th key={i} className="synergy-th">{p.player_name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, ri) => (
            <tr key={ri}>
              <td className="synergy-th">{players[ri].player_name}</td>
              {row.map((cell, ci) => {
                if (ri === ci) return <td key={ci} className="synergy-cell self">—</td>;
                const intensity = cell.matches / maxMatches;
                const bg = `rgba(74, 222, 128, ${intensity * 0.6})`;
                return (
                  <td key={ci} className="synergy-cell" style={{ background: bg }}>
                    {cell.matches}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="synergy-legend">
        <span>0</span>
        <div className="legend-gradient" />
        <span>{maxMatches}</span>
        <span className="muted-text">shared matches</span>
      </div>
    </div>
  );
}

export default function LineupBuilder() {
  const [slots, setSlots] = useState(Array(5).fill(null));
  const [result, setResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);

  const setPlayer = (index, player) => {
    const next = [...slots];
    next[index] = player;
    setSlots(next);
  };

  const clearPlayer = (index) => {
    const next = [...slots];
    next[index] = null;
    setSlots(next);
  };

  const allFilled = slots.every(s => s !== null);
  const ids = slots.map(s => s?.player_id);

  const doAnalyze = () => {
    if (!allFilled) return;
    setAnalyzing(true);
    setError(null);
    setResult(null);
    analyzeLineup(ids).then(data => {
      if (data.error) { setError(data.error); }
      else { setResult(data); }
      setAnalyzing(false);
    }).catch(() => { setError('Failed to analyze lineup'); setAnalyzing(false); });
  };

  return (
    <div>
      <h2 className="page-title">Lineup Builder</h2>
      <p className="page-desc">
        Select 5 players by position, then analyze their synergy, shared history, and similar lineups.
      </p>

      <div className="lineup-slots">
        {POSITIONS.map((pos, i) => (
          <PlayerSlot
            key={pos.key}
            position={pos}
            selected={slots[i]}
            onSelect={(p) => setPlayer(i, p)}
            onClear={() => clearPlayer(i)}
            takenIds={slots.filter(s => s !== null).map(s => s.player_id)}
          />
        ))}
      </div>

      <div className="lineup-actions">
        <button
          className="analyze-btn"
          disabled={!allFilled || analyzing}
          onClick={doAnalyze}
        >
          {analyzing ? 'Analyzing...' : 'Analyze Lineup'}
        </button>
        {allFilled && !analyzing && (
          <button className="reset-btn" onClick={() => { setSlots(Array(5).fill(null)); setResult(null); setError(null); }}>
            Reset
          </button>
        )}
      </div>

      {error && <div className="error" style={{ marginTop: 16 }}>{error}</div>}

      {result && (
        <div className="lineup-result">
          <div className="player-cards">
            {result.player_cards.map((pc, i) => (
              <div key={i} className="player-card">
                <div className="pc-position">{pc.position.toUpperCase()}</div>
                <div className="pc-name">{pc.player_name}</div>
                <div className="pc-stats">
                  <span>{pc.career_matches} matches</span>
                  <span className={pc.career_wr >= 0.55 ? 'winner' : pc.career_wr < 0.45 ? 'loser' : ''}>
                    {(pc.career_wr * 100).toFixed(1)}% WR
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="combined-stats">
            <h3>Combined Overview</h3>
            <div className="cs-grid">
              <div className="cs-item">
                <span className="cs-value">{(result.combined_stats.avg_wr * 100).toFixed(1)}%</span>
                <span className="cs-label">Avg Win Rate</span>
              </div>
              <div className="cs-item">
                <span className="cs-value">{result.combined_stats.total_experience.toLocaleString()}</span>
                <span className="cs-label">Total Career Games</span>
              </div>
              <div className="cs-item">
                <span className="cs-value">{result.combined_stats.total_wins.toLocaleString()}</span>
                <span className="cs-label">Total Career Wins</span>
              </div>
              <div className="cs-item">
                <span className={`cs-value ${result.position_fit ? 'good' : 'warn'}`}>
                  {result.position_fit ? 'Yes' : 'No'}
                </span>
                <span className="cs-label">Unique Positions</span>
              </div>
            </div>
          </div>

          {result.exact_lineup_history.matches > 0 && (
            <div className="lineup-history">
              <h3>Exact Lineup History</h3>
              <div className="cs-grid">
                <div className="cs-item">
                  <span className="cs-value">{result.exact_lineup_history.matches}</span>
                  <span className="cs-label">Matches Together</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value">{result.exact_lineup_history.wins}</span>
                  <span className="cs-label">Wins</span>
                </div>
                <div className="cs-item">
                  <span className={`cs-value ${result.exact_lineup_history.win_rate >= 0.55 ? 'winner' : result.exact_lineup_history.win_rate < 0.45 ? 'loser' : ''}`}>
                    {(result.exact_lineup_history.win_rate * 100).toFixed(1)}%
                  </span>
                  <span className="cs-label">Win Rate</span>
                </div>
              </div>
            </div>
          )}
          {result.exact_lineup_history.matches === 0 && (
            <div className="lineup-history">
              <h3>Exact Lineup History</h3>
              <p className="muted-text">
                This exact 5-man lineup has never played together before.
              </p>
            </div>
          )}

          <div className="synergy-section">
            <h3>Pair Synergy Matrix</h3>
            <p className="muted-text" style={{ marginBottom: 12 }}>
              Number of matches each pair of players has been on the same team.
            </p>
            <SynergyMatrix matrix={result.pair_synergy_matrix} players={result.player_cards} />
          </div>

          {result.similar_lineups.length > 0 && (
            <div className="similar-section">
              <h3>Similar Lineups</h3>
              <p className="muted-text" style={{ marginBottom: 12 }}>
                Historical lineups sharing 3+ players with this roster.
              </p>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Players</th>
                    <th>Overlap</th>
                    <th>Matches</th>
                    <th>Win Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {result.similar_lineups.map((sl, i) => (
                    <tr key={i}>
                      <td>{sl.player_names.join(', ')}</td>
                      <td>{sl.overlap}/5</td>
                      <td>{sl.matches}</td>
                      <td className={sl.win_rate >= 0.55 ? 'winner' : sl.win_rate < 0.45 ? 'loser' : ''}>
                        {(sl.win_rate * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

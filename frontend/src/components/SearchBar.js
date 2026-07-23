import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { globalSearch } from '../api';

export default function SearchBar() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const wrapperRef = useRef(null);
  const debounceRef = useRef(null);

  const doSearch = useCallback((val) => {
    if (val.length < 2) { setResults(null); return; }
    setLoading(true);
    globalSearch(val, 5).then(data => {
      setResults(data);
      setLoading(false);
      setOpen(true);
    }).catch(() => { setLoading(false); setResults(null); });
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(query), 300);
    return () => clearTimeout(debounceRef.current);
  }, [query, doSearch]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKey = (e) => {
    if (e.key === 'Escape') setOpen(false);
  };

  const goTo = (path) => {
    setOpen(false);
    setQuery('');
    navigate(path);
  };

  const hasResults = results && (
    results.teams.length > 0 || results.players.length > 0 || results.matches.length > 0
  );

  return (
    <div className="search-bar-wrapper" ref={wrapperRef}>
      <input
        className="global-search-input"
        placeholder="Search teams, players, matches..."
        value={query}
        onChange={e => setQuery(e.target.value)}
        onFocus={() => query.length >= 2 && results && setOpen(true)}
        onKeyDown={handleKey}
      />
      {loading && <span className="search-spinner">...</span>}

      {open && hasResults && (
        <div className="search-dropdown">
          {results.teams.length > 0 && (
            <div className="search-group">
              <div className="search-group-label">Teams</div>
              {results.teams.map((t, i) => (
                <div key={i} className="search-item" onClick={() => goTo(`/teams/${encodeURIComponent(t.name)}`)}>
                  <span className="search-item-icon">⚔</span>
                  <span>{t.name}</span>
                </div>
              ))}
            </div>
          )}

          {results.players.length > 0 && (
            <div className="search-group">
              <div className="search-group-label">Players</div>
              {results.players.map((p, i) => (
                <div key={i} className="search-item" onClick={() => goTo(`/players/${p.id}`)}>
                  <span className="search-item-icon">👤</span>
                  <span>{p.name}</span>
                </div>
              ))}
            </div>
          )}

          {results.matches.length > 0 && (
            <div className="search-group">
              <div className="search-group-label">Matches</div>
              {results.matches.map((m, i) => (
                <div key={i} className="search-item" onClick={() => goTo(`/matches/${m.id}`)}>
                  <span className="search-item-icon">🎮</span>
                  <span>{m.team1} vs {m.team2} ({m.score})</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {open && query.length >= 2 && !loading && !hasResults && (
        <div className="search-dropdown">
          <div className="search-empty">No results found</div>
        </div>
      )}
    </div>
  );
}

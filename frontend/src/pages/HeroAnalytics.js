import React, { useState, useEffect } from 'react';
import { getHeroes, getHeroDetail } from '../api';

const ATTRS = [
  { value: null, label: 'All' },
  { value: 'str', label: 'STR' },
  { value: 'agi', label: 'AGI' },
  { value: 'int', label: 'INT' },
  { value: 'all', label: 'ALL' },
];

const SORT_OPTIONS = [
  { value: 'pick_count', label: 'Most Picked' },
  { value: 'win_rate', label: 'Win Rate' },
  { value: 'avg_kills', label: 'Avg Kills' },
  { value: 'avg_gpm', label: 'Avg GPM' },
];

export default function HeroAnalytics() {
  const [heroes, setHeroes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sort, setSort] = useState('pick_count');
  const [attr, setAttr] = useState(null);
  const [selectedHero, setSelectedHero] = useState(null);
  const [heroDetail, setHeroDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getHeroes({ sort, attr: attr || undefined })
      .then(data => { setHeroes(data); setLoading(false); })
      .catch(() => { setError('Failed to load heroes'); setLoading(false); });
  }, [sort, attr]);

  const selectHero = (heroId) => {
    setSelectedHero(heroId);
    setDetailLoading(true);
    getHeroDetail(heroId)
      .then(data => { setHeroDetail(data); setDetailLoading(false); })
      .catch(() => { setHeroDetail(null); setDetailLoading(false); });
  };

  if (selectedHero) {
    return (
      <div>
        <button className="back-btn" onClick={() => { setSelectedHero(null); setHeroDetail(null); }}>
          ← Back to Heroes
        </button>
        {detailLoading ? <div className="loading">Loading hero details...</div> : (
          heroDetail && !heroDetail.error ? (
            <div className="hero-detail">
              <div className="hero-detail-header">
                <div>
                  <h2>{heroDetail.name}</h2>
                  <div className="hero-meta">
                    <span className={`hero-attr attr-${heroDetail.primary_attr}`}>{heroDetail.primary_attr?.toUpperCase()}</span>
                    <span className="hero-attack">{heroDetail.attack_type}</span>
                  </div>
                </div>
              </div>

              <div className="cs-grid section-gap">
                <div className="cs-item">
                  <span className="cs-value">{heroDetail.pick_count}</span>
                  <span className="cs-label">Picks</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value">{heroDetail.ban_count}</span>
                  <span className="cs-label">Bans</span>
                </div>
                <div className="cs-item">
                  <span className={`cs-value ${heroDetail.win_rate >= 0.52 ? 'good' : heroDetail.win_rate < 0.48 ? 'warn' : ''}`}>
                    {heroDetail.pick_count > 0 ? `${(heroDetail.win_rate * 100).toFixed(1)}%` : '—'}
                  </span>
                  <span className="cs-label">Win Rate</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value">{heroDetail.avg_kills || '—'}</span>
                  <span className="cs-label">Avg Kills</span>
                </div>
              </div>

              <div className="cs-grid section-gap">
                <div className="cs-item">
                  <span className="cs-value">{heroDetail.avg_deaths || '—'}</span>
                  <span className="cs-label">Avg Deaths</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value">{heroDetail.avg_assists || '—'}</span>
                  <span className="cs-label">Avg Assists</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value">{heroDetail.avg_gpm || '—'}</span>
                  <span className="cs-label">Avg GPM</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value">{heroDetail.avg_xpm || '—'}</span>
                  <span className="cs-label">Avg XPM</span>
                </div>
              </div>

              <div className="cs-grid">
                <div className="cs-item">
                  <span className="cs-value">{heroDetail.avg_lh || '—'}</span>
                  <span className="cs-label">Avg Last Hits</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value">{heroDetail.avg_denies || '—'}</span>
                  <span className="cs-label">Avg Denies</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value">{heroDetail.avg_dmg?.toLocaleString() || '—'}</span>
                  <span className="cs-label">Avg Hero Damage</span>
                </div>
                <div className="cs-item">
                  <span className="cs-value">{heroDetail.avg_nw?.toLocaleString() || '—'}</span>
                  <span className="cs-label">Avg Net Worth</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="error">{heroDetail?.error || 'Failed to load hero'}</div>
          )
        )}
      </div>
    );
  }

  return (
    <div className="page">
      <h2 className="page-title">Hero Analytics</h2>
      <p className="page-desc">
        Pick/ban rates, win rates, and performance stats from fetched match data.
      </p>

      <div className="controls">
        <select value={sort} onChange={e => setSort(e.target.value)} className="hero-filter-select">
          {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <div className="hero-attr-filter">
          {ATTRS.map(a => (
            <button
              key={a.value || 'all'}
              className={`hero-attr-btn ${attr === a.value ? 'active' : ''} ${a.value ? `attr-${a.value}` : ''}`}
              onClick={() => setAttr(a.value)}
            >
              {a.label}
            </button>
          ))}
        </div>
        <span className="count">{heroes.length} heroes</span>
      </div>

      {loading && <div className="loading">Loading heroes...</div>}
      {error && <div className="error">{error}</div>}

      {!loading && !error && heroes.length === 0 && (
        <div className="empty-state">No hero data yet. Fetching match data from OpenDota...</div>
      )}

      {!loading && !error && heroes.length > 0 && (
        <table className="data-table full-width">
          <thead>
            <tr>
              <th>#</th>
              <th>Hero</th>
              <th>Attr</th>
              <th>Picks</th>
              <th>Win Rate</th>
              <th>Avg K/D/A</th>
              <th>Avg GPM</th>
              <th>Avg LH</th>
            </tr>
          </thead>
          <tbody>
            {heroes.map((h, i) => (
              <tr key={h.hero_id} className="clickable-row" onClick={() => selectHero(h.hero_id)}>
                <td>{i + 1}</td>
                <td><strong>{h.name}</strong></td>
                <td><span className={`hero-attr attr-${h.primary_attr}`}>{h.primary_attr?.toUpperCase()}</span></td>
                <td>{h.pick_count}</td>
                <td className={h.win_rate >= 0.52 ? 'winner' : h.win_rate < 0.48 ? 'loser' : ''}>
                  {(h.win_rate * 100).toFixed(1)}%
                </td>
                <td>{h.avg_kills}/{h.avg_deaths}/{h.avg_assists}</td>
                <td>{h.avg_gpm}</td>
                <td>{h.avg_lh}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

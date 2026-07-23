import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getMatchDetail, getHeroes } from '../api';

const GAME_MODES = {
  0: 'Unknown', 1: 'All Pick', 2: 'Single Draft', 3: 'All Random',
  16: "Captain's Draft", 18: 'Ability Draft', 22: "Captain's Mode",
  23: 'All Pick', 24: 'Turbo',
};

function formatDuration(seconds) {
  if (!seconds) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

function formatDate(ts) {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleDateString();
}

export default function MatchDetail() {
  const { matchId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [heroMap, setHeroMap] = useState({});

  useEffect(() => {
    getHeroes({}).then(heroes => {
      const map = {};
      heroes.forEach(h => { map[h.hero_id] = h.localized_name || h.name; });
      setHeroMap(map);
    }).catch(() => { setHeroMap({}); });
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getMatchDetail(matchId)
      .then(d => { setData(d); setLoading(false); })
      .catch(() => { setError('Failed to load match detail'); setLoading(false); });
  }, [matchId]);

  if (loading) return <div className="loading">Loading match detail...</div>;
  if (error) return <div className="error">{error}</div>;
  if (data?.error) return (
    <div>
      <button className="back-btn" onClick={() => navigate('/matches')}>← Back to Matches</button>
      <div className="error">{data.error}</div>
    </div>
  );
  if (!data) return null;

  const radiantPlayers = (data.players || []).filter(p => p.team === 'radiant');
  const direPlayers = (data.players || []).filter(p => p.team === 'dire');

  return (
    <div>
      <button className="back-btn" onClick={() => navigate('/matches')}>← Back to Matches</button>

      <div className="match-detail">
        <div className="md-header">
          <div className="md-teams">
            <div className={`md-team-block ${data.radiant_win ? 'md-winner' : ''}`}>
              <div className="md-team-label">Radiant</div>
              <div className="md-team-name">{data.team1}</div>
              <div className="md-team-score">{data.radiant_score}</div>
            </div>
            <div className="md-vs">VS</div>
            <div className={`md-team-block ${!data.radiant_win ? 'md-winner' : ''}`}>
              <div className="md-team-label">Dire</div>
              <div className="md-team-name">{data.team2}</div>
              <div className="md-team-score">{data.dire_score}</div>
            </div>
          </div>
          <div className="md-meta">
            <span>{formatDuration(data.duration)}</span>
            <span>{GAME_MODES[data.game_mode] || `Mode ${data.game_mode}`}</span>
            <span>{data.tournament}</span>
            <span>{data.datetime ? new Date(data.datetime).toLocaleDateString() : formatDate(data.start_time)}</span>
          </div>
        </div>

        {data.picks_bans && data.picks_bans.length > 0 && (
          <div className="section section-gap">
            <h3>Draft</h3>
            <div className="draft-list">
              {data.picks_bans.map((pb, i) => (
                <span key={i} className={`draft-item ${pb.is_pick ? 'draft-pick' : 'draft-ban'} draft-team-${pb.team}`}>
                  {pb.is_pick ? 'P' : 'B'} {heroMap[pb.hero_id] || `Hero ${pb.hero_id}`}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="md-players-grid">
          <div className="section">
            <h3 className="md-section-title md-radiant">Radiant</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Hero</th><th>K</th><th>D</th><th>A</th><th>GPM</th><th>XPM</th>
                  <th>LH</th><th>DN</th><th>DMG</th><th>Tower</th><th>NW</th>
                </tr>
              </thead>
              <tbody>
                {radiantPlayers.map((p, i) => (
                  <tr key={i} className={p.win ? 'match-winner-row' : ''}>
                    <td><strong>{p.hero_name}</strong></td>
                    <td>{p.kills}</td>
                    <td>{p.deaths}</td>
                    <td>{p.assists}</td>
                    <td>{p.gold_per_min}</td>
                    <td>{p.xp_per_min}</td>
                    <td>{p.last_hits}</td>
                    <td>{p.denies}</td>
                    <td>{p.hero_damage?.toLocaleString()}</td>
                    <td>{p.tower_damage?.toLocaleString()}</td>
                    <td>{p.net_worth?.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="section">
            <h3 className="md-section-title md-dire">Dire</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Hero</th><th>K</th><th>D</th><th>A</th><th>GPM</th><th>XPM</th>
                  <th>LH</th><th>DN</th><th>DMG</th><th>Tower</th><th>NW</th>
                </tr>
              </thead>
              <tbody>
                {direPlayers.map((p, i) => (
                  <tr key={i} className={p.win ? 'match-winner-row' : ''}>
                    <td><strong>{p.hero_name}</strong></td>
                    <td>{p.kills}</td>
                    <td>{p.deaths}</td>
                    <td>{p.assists}</td>
                    <td>{p.gold_per_min}</td>
                    <td>{p.xp_per_min}</td>
                    <td>{p.last_hits}</td>
                    <td>{p.denies}</td>
                    <td>{p.hero_damage?.toLocaleString()}</td>
                    <td>{p.tower_damage?.toLocaleString()}</td>
                    <td>{p.net_worth?.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

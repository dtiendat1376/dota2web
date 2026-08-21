import React, { useState, useEffect } from 'react';
import { getTeams, getH2H, predict } from '../api';

export default function H2HPredict() {
  const [teams, setTeams] = useState([]);
  const [team1, setTeam1] = useState('');
  const [team2, setTeam2] = useState('');
  const [h2hResult, setH2hResult] = useState(null);
  const [predResult, setPredResult] = useState(null);
  const [activeTab, setActiveTab] = useState('h2h');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getTeams().then(setTeams).catch(() => {});
  }, []);

  const doAnalyze = () => {
    if (!team1 || !team2 || team1 === team2) return;
    setLoading(true);
    setH2hResult(null);
    setPredResult(null);

    Promise.all([
      getH2H(team1, team2).catch(() => null),
      predict(team1, team2).catch(() => null),
    ]).then(([h2h, pred]) => {
      setH2hResult(h2h);
      setPredResult(pred);
      setLoading(false);
    });
  };

  const swapTeams = () => {
    setTeam1(team2);
    setTeam2(team1);
    setH2hResult(null);
    setPredResult(null);
  };

  const confidenceClass = (conf) => conf > 0.3 ? 'high' : conf > 0.15 ? 'medium' : 'low';

  return (
    <div>
      <h2 className="page-title">Head-to-Head & Predictions</h2>
      <p className="page-desc">
        Compare two teams and get a match prediction with detailed feature breakdown.
      </p>

      <div className="predict-form">
        <div className="team-select">
          <label>Team 1</label>
          <select value={team1} onChange={e => setTeam1(e.target.value)}>
            <option value="">Select team...</option>
            {teams.map(t => <option key={t.team_name} value={t.team_name}>{t.team_name}</option>)}
          </select>
        </div>
        <button className="swap-btn" onClick={swapTeams} title="Swap teams">⇄</button>
        <div className="vs">VS</div>
        <div className="team-select">
          <label>Team 2</label>
          <select value={team2} onChange={e => setTeam2(e.target.value)}>
            <option value="">Select team...</option>
            {teams.map(t => <option key={t.team_name} value={t.team_name}>{t.team_name}</option>)}
          </select>
        </div>
        <button
          className="predict-btn"
          onClick={doAnalyze}
          disabled={loading || !team1 || !team2 || team1 === team2}
        >
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
      </div>

      {team1 && team2 && team1 === team2 && (
        <div className="error" style={{ marginBottom: 16 }}>Please select two different teams.</div>
      )}

      {(h2hResult || predResult) && (
        <div className="h2h-predict-result">
          <div className="h2h-tabs">
            <button
              className={`h2h-tab ${activeTab === 'h2h' ? 'active' : ''}`}
              onClick={() => setActiveTab('h2h')}
            >
              Head-to-Head
              {h2hResult && h2hResult.error && <span className="tab-error"> (!)</span>}
            </button>
            <button
              className={`h2h-tab ${activeTab === 'predict' ? 'active' : ''}`}
              onClick={() => setActiveTab('predict')}
            >
              Prediction
              {predResult && predResult.error && <span className="tab-error"> (!)</span>}
            </button>
          </div>

          {activeTab === 'h2h' && h2hResult && !h2hResult.error && (
            <div className="h2h-content">
              <div className="h2h-scoreboard">
                <div className="h2h-team-block">
                  <div className="h2h-team-name">{h2hResult.team1}</div>
                  <div className="h2h-team-wins">{h2hResult.team1_wins}</div>
                </div>
                <div className="h2h-center">
                  <div className="h2h-total">{h2hResult.total_matches} matches</div>
                  <div className="h2h-avg-diff">Avg diff: {h2hResult.h2h_score_diff > 0 ? '+' : ''}{h2hResult.h2h_score_diff}</div>
                  {h2hResult.roster_overlap > 0 && (
                    <div className="h2h-overlap">Roster overlap: {h2hResult.roster_overlap} players</div>
                  )}
                </div>
                <div className="h2h-team-block">
                  <div className="h2h-team-name">{h2hResult.team2}</div>
                  <div className="h2h-team-wins">{h2hResult.team2_wins}</div>
                </div>
              </div>

              <div className="prob-bars" style={{ marginTop: 20 }}>
                <div className="prob-bar">
                  <span>{h2hResult.team1}</span>
                  <div className="bar-bg">
                    <div className="bar-fill t1" style={{ width: `${h2hResult.team1_wr * 100}%` }}>
                      {(h2hResult.team1_wr * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
                <div className="prob-bar">
                  <span>{h2hResult.team2}</span>
                  <div className="bar-bg">
                    <div className="bar-fill t2" style={{ width: `${h2hResult.team2_wr * 100}%` }}>
                      {(h2hResult.team2_wr * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
              </div>

              {h2hResult.last5 && h2hResult.last5.total > 0 && (
                <div className="section section-gap">
                  <h3>Last 5 Meetings</h3>
                  <div className="cs-grid">
                    <div className="cs-item">
                      <span className="cs-value">{h2hResult.last5.total}</span>
                      <span className="cs-label">Total</span>
                    </div>
                    <div className="cs-item">
                      <span className="cs-value">{h2hResult.last5.team1_wins}</span>
                      <span className="cs-label">{h2hResult.team1} Wins</span>
                    </div>
                    <div className="cs-item">
                      <span className="cs-value">{h2hResult.last5.team2_wins}</span>
                      <span className="cs-label">{h2hResult.team2} Wins</span>
                    </div>
                  </div>
                </div>
              )}

              {h2hResult.match_history && h2hResult.match_history.length > 0 && (
                <div className="section">
                  <h3>Recent Match History</h3>
                  <table className="data-table">
                    <thead>
                      <tr><th>Date</th><th>Tournament</th><th>{h2hResult.team1}</th><th>Score</th><th>{h2hResult.team2}</th><th>Bo</th></tr>
                    </thead>
                    <tbody>
                      {h2hResult.match_history.map((m, i) => (
                        <tr key={i}>
                          <td className="meta-cell">
                            {m.date ? new Date(m.date).toLocaleDateString() : '—'}
                          </td>
                          <td>{m.tournament}</td>
                          <td className={m.winner === h2hResult.team1 ? 'winner' : ''}>{m.team1}</td>
                          <td className="score">{m.score}{!m.winner && <span className="draw-badge">Draw</span>}</td>
                          <td className={m.winner === h2hResult.team2 ? 'winner' : ''}>{m.team2}</td>
                          <td className="muted-text">Bo{m.best_of}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {activeTab === 'predict' && predResult && !predResult.error && (
            <div className="h2h-content">
              <div className="prediction-result" style={{ border: 'none', padding: 0, background: 'transparent' }}>
                <h2>{predResult.predicted_winner} wins!</h2>

                <span className={`confidence-badge ${confidenceClass(predResult.confidence)}`}>
                  Confidence: {(predResult.confidence * 100).toFixed(0)}%
                </span>

                <div className="prob-bars">
                  <div className="prob-bar">
                    <span>{predResult.team1}</span>
                    <div className="bar-bg">
                      <div className="bar-fill t1" style={{ width: `${predResult.team1_win_probability * 100}%` }}>
                        {(predResult.team1_win_probability * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                  <div className="prob-bar">
                    <span>{predResult.team2}</span>
                    <div className="bar-bg">
                      <div className="bar-fill t2" style={{ width: `${predResult.team2_win_probability * 100}%` }}>
                        {(predResult.team2_win_probability * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                </div>

                {predResult.features && (
                  <div className="features-grid" style={{ marginTop: 24 }}>
                    <div className="feature-col">
                      <h3>{predResult.team1}</h3>
                      <div className="feature-section">
                        <span className="feature-section-label">Form</span>
                        <p>Win Rate: {(predResult.features.team1.win_rate * 100).toFixed(1)}%</p>
                        <p>Decay WR: {(predResult.features.team1.roster_decay_wr * 100).toFixed(1)}%</p>
                        <p>Bo3 WR: {(predResult.features.team1.bo3_wr * 100).toFixed(1)}%</p>
                        <p>Streak: {predResult.features.team1.streak > 0 ? `W${predResult.features.team1.streak}` : `L${Math.abs(predResult.features.team1.streak)}`}</p>
                      </div>
                      <div className="feature-section">
                        <span className="feature-section-label">Momentum</span>
                        <p>Score Diff: {predResult.features.team1.avg_score_diff > 0 ? '+' : ''}{predResult.features.team1.avg_score_diff}</p>
                        <p>Recent 10 Diff: {predResult.features.team1.recent_10_score_diff > 0 ? '+' : ''}{predResult.features.team1.recent_10_score_diff}</p>
                      </div>
                      <div className="feature-section">
                        <span className="feature-section-label">Activity</span>
                        <p>Matches (90d): {predResult.features.team1.match_frequency_90d}</p>
                        <p>Roster Age: {predResult.features.team1.roster_days}d</p>
                        <p>Days Since Match: {predResult.features.team1.days_since_last}d</p>
                        <p>Total: {predResult.features.team1.total_matches}</p>
                      </div>
                    </div>
                    <div className="feature-col">
                      <h3>H2H</h3>
                      <div className="feature-section">
                        <span className="feature-section-label">Overall</span>
                        <p>Matches: {predResult.features.h2h.total_matches}</p>
                        <p>{predResult.team1} WR: {(predResult.features.h2h.team1_wr * 100).toFixed(1)}%</p>
                        <p>Score Diff: {predResult.features.h2h.score_diff > 0 ? '+' : ''}{predResult.features.h2h.score_diff}</p>
                      </div>
                      <div className="feature-section">
                        <span className="feature-section-label">Recent</span>
                        <p>Recent 10 WR: {(predResult.features.h2h.recent_10_wr * 100).toFixed(1)}%</p>
                        <p>Roster Overlap: {predResult.features.h2h.roster_overlap} players</p>
                      </div>
                    </div>
                    <div className="feature-col">
                      <h3>{predResult.team2}</h3>
                      <div className="feature-section">
                        <span className="feature-section-label">Form</span>
                        <p>Win Rate: {(predResult.features.team2.win_rate * 100).toFixed(1)}%</p>
                        <p>Decay WR: {(predResult.features.team2.roster_decay_wr * 100).toFixed(1)}%</p>
                        <p>Bo3 WR: {(predResult.features.team2.bo3_wr * 100).toFixed(1)}%</p>
                        <p>Streak: {predResult.features.team2.streak > 0 ? `W${predResult.features.team2.streak}` : `L${Math.abs(predResult.features.team2.streak)}`}</p>
                      </div>
                      <div className="feature-section">
                        <span className="feature-section-label">Momentum</span>
                        <p>Score Diff: {predResult.features.team2.avg_score_diff > 0 ? '+' : ''}{predResult.features.team2.avg_score_diff}</p>
                        <p>Recent 10 Diff: {predResult.features.team2.recent_10_score_diff > 0 ? '+' : ''}{predResult.features.team2.recent_10_score_diff}</p>
                      </div>
                      <div className="feature-section">
                        <span className="feature-section-label">Activity</span>
                        <p>Matches (90d): {predResult.features.team2.match_frequency_90d}</p>
                        <p>Roster Age: {predResult.features.team2.roster_days}d</p>
                        <p>Days Since Match: {predResult.features.team2.days_since_last}d</p>
                        <p>Total: {predResult.features.team2.total_matches}</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'h2h' && !h2hResult && predResult && (
            <div className="empty-state" style={{ padding: 24 }}>H2H data unavailable for these teams.</div>
          )}
          {activeTab === 'predict' && !predResult && h2hResult && (
            <div className="empty-state" style={{ padding: 24 }}>Prediction unavailable for these teams.</div>
          )}

          {h2hResult && h2hResult.error && activeTab === 'h2h' && (
            <div className="error" style={{ marginTop: 16 }}>{h2hResult.error}</div>
          )}
          {predResult && predResult.error && activeTab === 'predict' && (
            <div className="error" style={{ marginTop: 16 }}>{predResult.error}</div>
          )}
        </div>
      )}
    </div>
  );
}

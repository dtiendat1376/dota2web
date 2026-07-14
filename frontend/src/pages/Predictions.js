import React, { useState, useEffect } from 'react';
import { predict, getTeams } from '../api';

function Predictions() {
  const [teams, setTeams] = useState([]);
  const [team1, setTeam1] = useState('');
  const [team2, setTeam2] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getTeams().then(setTeams);
  }, []);

  const handlePredict = async () => {
    if (!team1 || !team2) return;
    setLoading(true);
    try {
      const data = await predict(team1, team2);
      setResult(data);
    } catch (e) {
      setResult({ error: 'Prediction failed' });
    }
    setLoading(false);
  };

  return (
    <div className="page">
      <h1>Match Prediction</h1>

      <div className="predict-form">
        <div className="team-select">
          <label>Team 1</label>
          <select value={team1} onChange={e => setTeam1(e.target.value)}>
            <option value="">Select team...</option>
            {teams.map(t => <option key={t.team_name} value={t.team_name}>{t.team_name}</option>)}
          </select>
        </div>
        <div className="vs">VS</div>
        <div className="team-select">
          <label>Team 2</label>
          <select value={team2} onChange={e => setTeam2(e.target.value)}>
            <option value="">Select team...</option>
            {teams.map(t => <option key={t.team_name} value={t.team_name}>{t.team_name}</option>)}
          </select>
        </div>
        <button onClick={handlePredict} disabled={loading || !team1 || !team2} className="predict-btn">
          {loading ? 'Predicting...' : 'Predict'}
        </button>
      </div>

      {result && !result.error && (
        <div className="prediction-result">
          <h2>{result.predicted_winner} wins!</h2>
          <div className="prob-bars">
            <div className="prob-bar">
              <span>{result.team1}</span>
              <div className="bar-bg">
                <div className="bar-fill t1" style={{ width: `${result.team1_win_probability * 100}%` }}>
                  {(result.team1_win_probability * 100).toFixed(1)}%
                </div>
              </div>
            </div>
            <div className="prob-bar">
              <span>{result.team2}</span>
              <div className="bar-bg">
                <div className="bar-fill t2" style={{ width: `${result.team2_win_probability * 100}%` }}>
                  {(result.team2_win_probability * 100).toFixed(1)}%
                </div>
              </div>
            </div>
          </div>

          {result.features && (
            <div className="features-grid">
              <div className="feature-col">
                <h3>{result.team1}</h3>
                <p>Win Rate: {(result.features.team1.win_rate * 100).toFixed(1)}%</p>
                <p>Last 5: {(result.features.team1.recent_5_wr * 100).toFixed(1)}%</p>
                <p>Last 10: {(result.features.team1.recent_10_wr * 100).toFixed(1)}%</p>
                <p>Streak: {result.features.team1.streak > 0 ? `W${result.features.team1.streak}` : `L${Math.abs(result.features.team1.streak)}`}</p>
              </div>
              <div className="feature-col">
                <h3>Head-to-Head</h3>
                <p>Matches: {result.features.h2h_matches}</p>
                <p>{result.team1} wins: {result.features.h2h_team1_wins}</p>
                <p>{result.team2} wins: {result.features.h2h_matches - result.features.h2h_team1_wins}</p>
              </div>
              <div className="feature-col">
                <h3>{result.team2}</h3>
                <p>Win Rate: {(result.features.team2.win_rate * 100).toFixed(1)}%</p>
                <p>Last 5: {(result.features.team2.recent_5_wr * 100).toFixed(1)}%</p>
                <p>Last 10: {(result.features.team2.recent_10_wr * 100).toFixed(1)}%</p>
                <p>Streak: {result.features.team2.streak > 0 ? `W${result.features.team2.streak}` : `L${Math.abs(result.features.team2.streak)}`}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {result && result.error && (
        <div className="error">{result.error}</div>
      )}
    </div>
  );
}

export default Predictions;

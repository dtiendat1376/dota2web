import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: API_BASE });

export const getStats = () => api.get('/api/stats').then(r => r.data);
export const getMatches = (params) => api.get('/api/matches/', { params }).then(r => r.data);
export const getMatch = (id) => api.get(`/api/matches/${id}`).then(r => r.data);
export const getTeamStats = (name) => api.get(`/api/matches/team/${name}/stats`).then(r => r.data);
export const getLeaderboard = (limit = 20) => api.get('/api/teams/leaderboard', { params: { limit } }).then(r => r.data);
export const getTeams = () => api.get('/api/teams/').then(r => r.data);
export const searchPlayers = (search, limit = 20) => api.get('/api/players/', { params: { search, limit } }).then(r => r.data);
export const predict = (team1, team2) => api.post('/api/predictions/predict', { team1, team2 }).then(r => r.data);
export const getPredictionHistory = () => api.get('/api/predictions/history').then(r => r.data);

export const getTournaments = () => api.get('/api/tournaments/').then(r => r.data);
export const getTournamentDetail = (id) => api.get(`/api/tournaments/${id}`).then(r => r.data);
export const getTournamentStandings = (id) => api.get(`/api/tournaments/${id}/standings`).then(r => r.data);
export const analyzeLineup = (player_ids) => api.post('/api/lineup/analyze', { player_ids }).then(r => r.data);
export const findSimilarLineups = (player_ids, limit = 10) => api.post('/api/lineup/similar', { player_ids, limit }).then(r => r.data);
export default api;

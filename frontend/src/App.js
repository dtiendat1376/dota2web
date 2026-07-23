import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Matches from './pages/Matches';
import MatchDetail from './pages/MatchDetail';
import Players from './pages/Players';
import Teams from './pages/Teams';
import H2HPredict from './pages/H2HPredict';
import Tournaments from './pages/Tournaments';
import LineupBuilder from './pages/LineupBuilder';
import HeroAnalytics from './pages/HeroAnalytics';
import SearchBar from './components/SearchBar';
import './App.css';

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/matches', label: 'Matches' },
  { to: '/teams', label: 'Teams' },
  { to: '/players', label: 'Players' },
  { to: '/tournaments', label: 'Tournaments' },
  { to: '/heroes', label: 'Heroes' },
  { to: '/h2h', label: 'H2H & Predict' },
  { to: '/lineup', label: 'Lineup Builder' },
];

function Navbar() {
  const location = useLocation();
  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">
        <img src="/logo.svg" alt="Dota 2" className="nav-logo" />
      </Link>
      <SearchBar />
      <div className="nav-links">
        {NAV_ITEMS.map(item => (
          <Link key={item.to} to={item.to} className={item.to !== '/' && location.pathname.startsWith(item.to) ? 'active' : location.pathname === item.to ? 'active' : ''}>
            {item.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}

function App() {
  return (
    <Router>
      <div className="App">
        <Navbar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/matches" element={<Matches />} />
            <Route path="/matches/:matchId" element={<MatchDetail />} />
            <Route path="/teams" element={<Teams />} />
            <Route path="/teams/:teamName" element={<Teams />} />
            <Route path="/players" element={<Players />} />
            <Route path="/players/:playerId" element={<Players />} />
            <Route path="/tournaments" element={<Tournaments />} />
            <Route path="/heroes" element={<HeroAnalytics />} />
            <Route path="/h2h" element={<H2HPredict />} />
            <Route path="/lineup" element={<LineupBuilder />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;

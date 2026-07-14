import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Matches from './pages/Matches';
import Predictions from './pages/Predictions';
import Tournaments from './pages/Tournaments';
import LineupBuilder from './pages/LineupBuilder';
import './App.css';

function App() {
  return (
    <Router>
      <div className="App">
        <nav className="navbar">
          <Link to="/" className="nav-brand">
            <img src="/logo.svg" alt="Dota 2" className="nav-logo" />
          </Link>
          <div className="nav-links">
            <Link to="/">Dashboard</Link>
            <Link to="/matches">Matches</Link>
            <Link to="/tournaments">Tournaments</Link>
            <Link to="/lineup">Lineup Builder</Link>
            <Link to="/predict">Predict</Link>
          </div>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/matches" element={<Matches />} />
            <Route path="/tournaments" element={<Tournaments />} />
            <Route path="/lineup" element={<LineupBuilder />} />
            <Route path="/predict" element={<Predictions />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;

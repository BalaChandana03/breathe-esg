import React, { useState } from 'react';
import Dashboard from './components/Dashboard';
import ReviewPortal from './components/ReviewPortal';
import { Leaf, BarChart2, CheckSquare } from 'lucide-react';
import './index.css';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  return (
    <div className="app-container">
      {/* Dynamic Design Header Navbar */}
      <header className="navbar">
        <div className="logo-container">
          <Leaf size={24} style={{ color: '#10b981' }} />
          <span className="logo-text">Breathe ESG</span>
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#059669', background: 'rgba(16, 185, 129, 0.1)', padding: '0.15rem 0.4rem', borderRadius: '4px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Enterprise Ingestor
          </span>
        </div>

        {/* Dynamic Navigation Tabs */}
        <nav className="nav-links">
          <button 
            onClick={() => setActiveTab('dashboard')}
            className={`nav-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
          >
            <BarChart2 size={16} /> Analytics Dashboard
          </button>
          <button 
            onClick={() => setActiveTab('review')}
            className={`nav-tab ${activeTab === 'review' ? 'active' : ''}`}
          >
            <CheckSquare size={16} /> Analyst Review Portal
          </button>
        </nav>
      </header>

      {/* Main Responsive Grid Panel */}
      <main className="main-content">
        {activeTab === 'dashboard' ? (
          <Dashboard />
        ) : (
          <ReviewPortal />
        )}
      </main>

      {/* Modern Sleek Footer */}
      <footer style={{ borderTop: '1px solid var(--border-color)', padding: '1.5rem 2rem', textAlign: 'center', fontSize: '0.8rem', color: '#6b7280', background: '#090d16' }}>
        <div>🍃 Breathe ESG Ingestion System &copy; {new Date().getFullYear()}</div>
        <div style={{ marginTop: '0.25rem' }}>Prototype developed in Django REST Framework &amp; React. Locked for audit compatibility.</div>
      </footer>
    </div>
  );
}

export default App;

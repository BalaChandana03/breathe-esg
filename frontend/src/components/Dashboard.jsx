import React, { useState, useEffect } from 'react';
import { Leaf, AlertTriangle, CheckCircle, RefreshCw, BarChart2, ShieldAlert, Layers, Building } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'https://breathe-esg-production-3a4b.up.railway.app';

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/analytics/`);
      if (!response.ok) {
        throw new Error('Failed to retrieve analytics from server.');
      }
      const result = await response.json();
      setData(result);
      setError(null);
    } catch (err) {
      console.error(err);
      setError('Could not connect to Django API. Make sure the backend server is running and accessible.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: '1rem' }}>
        <RefreshCw size={40} className="pulse-glow" style={{ color: '#10b981', animation: 'spin 2s linear infinite' }} />
        <p style={{ color: '#9ca3af' }}>Consolidating emissions ledgers...</p>
        <style>{`
          @keyframes spin { 100% { transform: rotate(360deg); } }
        `}</style>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', margin: '2rem auto', maxWidth: '600px', borderColor: '#ef4444' }}>
        <ShieldAlert size={48} style={{ color: '#ef4444', marginBottom: '1rem' }} />
        <h3 style={{ margin: '0 0 0.5rem 0' }}>API Connection Offline</h3>
        <p style={{ color: '#9ca3af', fontSize: '0.95rem', marginBottom: '1.5rem' }}>{error}</p>
        <button onClick={fetchAnalytics} className="btn btn-secondary">
          <RefreshCw size={16} /> Retry Connection
        </button>
      </div>
    );
  }

  const {
    total_emissions,
    scope_1,
    scope_2,
    scope_3,
    source_breakdown = {},
    facility_breakdown = [],
    monthly_trends = [],
    ingestion_stats = {}
  } = data || {};

  // Formulate calculations for visual displays
  const total = parseFloat(total_emissions) || 0;
  const s1Val = parseFloat(scope_1) || 0;
  const s2Val = parseFloat(scope_2) || 0;
  const s3Val = parseFloat(scope_3) || 0;

  const s1Pct = total > 0 ? (s1Val / total) * 100 : 0;
  const s2Pct = total > 0 ? (s2Val / total) * 100 : 0;
  const s3Pct = total > 0 ? (s3Val / total) * 100 : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      
      {/* 1. Header Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '2rem', fontWeight: 800 }}>Emissions & Ingestion Overview</h1>
          <p style={{ margin: '0.25rem 0 0 0', color: '#9ca3af' }}>Real-time Scope 1, 2, and 3 carbon accounting dashboard.</p>
        </div>
        <button onClick={fetchAnalytics} className="btn btn-secondary" style={{ height: 'fit-content' }}>
          <RefreshCw size={14} /> Refresh Data
        </button>
      </div>

      {/* 2. Top Aggregates Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1.5rem' }}>
        
        {/* Total Carbon Footprint Card */}
        <div className="glass-panel pulse-glow" style={{ padding: '1.5rem', position: 'relative', overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span style={{ color: '#34d399', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Footprint</span>
            <div style={{ padding: '0.5rem', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '8px', color: '#10b981' }}>
              <Leaf size={20} />
            </div>
          </div>
          <h2 style={{ margin: '0 0 0.25rem 0', fontSize: '2.2rem', fontWeight: 800 }}>{total.toFixed(2)}</h2>
          <span style={{ color: '#9ca3af', fontSize: '0.85rem' }}>Metric Tons CO₂e</span>
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: '4px', background: 'linear-gradient(90deg, #34d399, #10b981)' }}></div>
        </div>

        {/* Scope 1 Card */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span style={{ color: '#fbbf24', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Scope 1 (Direct Fuel)</span>
            <div style={{ padding: '0.5rem', background: 'rgba(245, 158, 11, 0.1)', borderRadius: '8px', color: '#f59e0b' }}>
              <Layers size={18} />
            </div>
          </div>
          <h3 style={{ margin: '0 0 0.25rem 0', fontSize: '1.8rem', fontWeight: 700 }}>{s1Val.toFixed(2)} <span style={{ fontSize: '1rem', color: '#9ca3af', fontWeight: 'normal' }}>t</span></h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.75rem' }}>
            <div style={{ flex: 1, height: '6px', background: '#1f2937', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ width: `${s1Pct}%`, height: '100%', background: '#fbbf24' }}></div>
            </div>
            <span style={{ color: '#9ca3af', fontSize: '0.8rem', fontWeight: 600 }}>{s1Pct.toFixed(0)}%</span>
          </div>
        </div>

        {/* Scope 2 Card */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span style={{ color: '#60a5fa', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Scope 2 (Electricity)</span>
            <div style={{ padding: '0.5rem', background: 'rgba(59, 130, 246, 0.1)', borderRadius: '8px', color: '#3b82f6' }}>
              <Layers size={18} />
            </div>
          </div>
          <h3 style={{ margin: '0 0 0.25rem 0', fontSize: '1.8rem', fontWeight: 700 }}>{s2Val.toFixed(2)} <span style={{ fontSize: '1rem', color: '#9ca3af', fontWeight: 'normal' }}>t</span></h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.75rem' }}>
            <div style={{ flex: 1, height: '6px', background: '#1f2937', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ width: `${s2Pct}%`, height: '100%', background: '#3b82f6' }}></div>
            </div>
            <span style={{ color: '#9ca3af', fontSize: '0.8rem', fontWeight: 600 }}>{s2Pct.toFixed(0)}%</span>
          </div>
        </div>

        {/* Scope 3 Card */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span style={{ color: '#a78bfa', fontWeight: 600, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Scope 3 (Travel & Proc)</span>
            <div style={{ padding: '0.5rem', background: 'rgba(139, 92, 246, 0.1)', borderRadius: '8px', color: '#8b5cf6' }}>
              <Layers size={18} />
            </div>
          </div>
          <h3 style={{ margin: '0 0 0.25rem 0', fontSize: '1.8rem', fontWeight: 700 }}>{s3Val.toFixed(2)} <span style={{ fontSize: '1rem', color: '#9ca3af', fontWeight: 'normal' }}>t</span></h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.75rem' }}>
            <div style={{ flex: 1, height: '6px', background: '#1f2937', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{ width: `${s3Pct}%`, height: '100%', background: '#8b5cf6' }}></div>
            </div>
            <span style={{ color: '#9ca3af', fontSize: '0.8rem', fontWeight: 600 }}>{s3Pct.toFixed(0)}%</span>
          </div>
        </div>

      </div>

      {/* 3. Ingestion Health & Anomalies Bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.5rem' }}>
        
        {/* Ledger Rows Count */}
        <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ padding: '0.5rem', background: 'rgba(255, 255, 255, 0.05)', borderRadius: '8px', color: '#9ca3af' }}>
            <BarChart2 size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', color: '#9ca3af', fontWeight: 500 }}>Ledger Rows Ingested</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{ingestion_stats.total_records || 0}</div>
          </div>
        </div>

        {/* Audit Sign-off Progress */}
        <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ padding: '0.5rem', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '8px', color: '#10b981' }}>
            <CheckCircle size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', color: '#9ca3af', fontWeight: 500 }}>Approved & Locked</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>
              {ingestion_stats.approved || 0}
              <span style={{ fontSize: '0.9rem', color: '#9ca3af', fontWeight: 'normal', marginLeft: '0.35rem' }}>
                / {ingestion_stats.total_records || 0}
              </span>
            </div>
          </div>
        </div>

        {/* Flagged Anomalies Alert */}
        <div className="glass-panel" style={{ padding: '1.25rem', display: 'flex', alignItems: 'center', gap: '1rem', borderColor: (ingestion_stats.anomalies > 0) ? 'rgba(245, 158, 11, 0.4)' : 'var(--border-color)' }}>
          <div style={{ padding: '0.5rem', background: (ingestion_stats.anomalies > 0) ? 'rgba(245, 158, 11, 0.15)' : 'rgba(255,255,255,0.05)', borderRadius: '8px', color: (ingestion_stats.anomalies > 0) ? '#f59e0b' : '#9ca3af' }}>
            <AlertTriangle size={24} />
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', color: '#9ca3af', fontWeight: 500 }}>Suspicious Rows (Flags)</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, color: (ingestion_stats.anomalies > 0) ? '#fbbf24' : 'var(--text-main)' }}>
              {ingestion_stats.anomalies || 0}
            </div>
          </div>
        </div>

      </div>

      {/* 4. Graphical Visualizations */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '2rem' }}>
        
        {/* Monthly Trend Area Chart (Pure SVG!) */}
        <div className="glass-panel" style={{ padding: '1.75rem' }}>
          <h3 style={{ margin: '0 0 1.5rem 0', fontSize: '1.1rem', fontWeight: 700 }}>Calendar-Aligned Monthly Ingestion Trend</h3>
          
          {monthly_trends.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '220px', color: '#9ca3af', fontSize: '0.9rem' }}>
              No calendar records finalized. Seed some files in the Review tab to view trends!
            </div>
          ) : (
            <div style={{ width: '100%' }}>
              {/* Responsive SVG Area Chart */}
              <svg viewBox="0 0 500 220" style={{ width: '100%', height: 'auto', overflow: 'visible' }}>
                <defs>
                  <linearGradient id="gradient-trend" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.3"/>
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0.0"/>
                  </linearGradient>
                </defs>
                
                {/* Grid Lines */}
                <line x1="40" y1="20" x2="480" y2="20" stroke="#1f2937" strokeWidth="1" strokeDasharray="3,3" />
                <line x1="40" y1="70" x2="480" y2="70" stroke="#1f2937" strokeWidth="1" strokeDasharray="3,3" />
                <line x1="40" y1="120" x2="480" y2="120" stroke="#1f2937" strokeWidth="1" strokeDasharray="3,3" />
                <line x1="40" y1="170" x2="480" y2="170" stroke="#1f2937" strokeWidth="1" />

                {/* Draw bar charts for each monthly segment */}
                {monthly_trends.map((t, idx) => {
                  const maxVal = Math.max(...monthly_trends.map(d => parseFloat(d.emissions) || 1)) || 1;
                  const itemVal = parseFloat(t.emissions) || 0;
                  
                  const width = 400 / monthly_trends.length;
                  const x = 40 + idx * width + width / 4;
                  const height = (itemVal / maxVal) * 140; // max height 140
                  const y = 170 - height;
                  
                  return (
                    <g key={idx} className="chart-bar-group">
                      {/* Interactive rect with tooltips */}
                      <rect 
                        x={x} 
                        y={y} 
                        width={width / 2} 
                        height={height} 
                        fill="url(#gradient-trend)"
                        stroke="#10b981"
                        strokeWidth="1.5"
                        rx="4"
                        style={{ cursor: 'pointer', transition: 'all 0.2s' }}
                      />
                      {/* Hover text displays value */}
                      <text x={x + width / 4} y={y - 8} fill="#34d399" fontSize="8" textAnchor="middle" fontWeight="bold">
                        {itemVal.toFixed(1)}t
                      </text>
                      {/* Label for X axis */}
                      <text x={x + width / 4} y="192" fill="#9ca3af" fontSize="8" textAnchor="middle">
                        {t.month}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          )}
        </div>

        {/* Facility-Level Disaggregation & Proportions */}
        <div className="glass-panel" style={{ padding: '1.75rem' }}>
          <h3 style={{ margin: '0 0 1.5rem 0', fontSize: '1.1rem', fontWeight: 700 }}>Emissions Disaggregation by Physical Facility</h3>
          
          {facility_breakdown.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '220px', color: '#9ca3af', fontSize: '0.9rem' }}>
              No facility assignments recorded.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', justifyContent: 'center', height: '100%', maxHeight: '240px' }}>
              {facility_breakdown.map((f, idx) => {
                const fVal = parseFloat(f.emissions) || 0;
                const fPct = total > 0 ? (fVal / total) * 100 : 0;
                
                // Color assignment helper
                const colors = ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6'];
                const color = colors[idx % colors.length];

                return (
                  <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: 600 }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Building size={14} style={{ color }} /> {f.facility}
                      </span>
                      <span>{fVal.toFixed(2)} t ({fPct.toFixed(0)}%)</span>
                    </div>
                    <div style={{ width: '100%', height: '8px', background: '#1f2937', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ width: `${fPct}%`, height: '100%', background: color, borderRadius: '4px' }}></div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>

    </div>
  );
}

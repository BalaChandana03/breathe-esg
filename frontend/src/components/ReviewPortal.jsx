import React, { useState, useEffect, useRef } from 'react';
import { Upload, HelpCircle, Filter, Edit3, Check, X, FileText, AlertTriangle, ChevronRight, CornerDownRight, History, MapPin, Sparkles, User, Calendar, RefreshCw } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'https://breathe-esg-production-3a4b.up.railway.app';

export default function ReviewPortal() {
  // Records State
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [facilities, setFacilities] = useState([]);

  // Filter State
  const [filterScope, setFilterScope] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterAnomaly, setFilterAnomaly] = useState(false);

  // Ingestion State
  const [uploadSourceType, setUploadSourceType] = useState('SAP');
  const [dragActive, setDragActive] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(null);
  const [uploadError, setUploadError] = useState(null);
  const fileInputRef = useRef(null);

  // Lineage Inspector Drawer State
  const [activeDrawerRecord, setActiveDrawerRecord] = useState(null);

  // Edit / Override State
  const [editingRecord, setEditingRecord] = useState(null);
  const [editQty, setEditQty] = useState('');
  const [editFacilityId, setEditFacilityId] = useState('');
  const [editError, setEditError] = useState(null);

  // Rejection Dialog State
  const [rejectingRecord, setRejectingRecord] = useState(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [rejectionError, setRejectionError] = useState(null);

  // Load records and facilities
  const fetchRecords = async () => {
    setLoading(true);
    try {
      // Build query string
      let url = `${API_BASE}/api/records/`;
      const params = [];
      if (filterScope) params.push(`scope=${filterScope}`);
      if (filterSource) params.push(`source_type=${filterSource}`);
      if (filterStatus) params.push(`status=${filterStatus}`);
      if (filterAnomaly) params.push(`has_anomalies=true`);
      
      if (params.length > 0) {
        url += `?${params.join('&')}`;
      }

      const response = await fetch(url);
      if (!response.ok) throw new Error('Failed to retrieve activity records.');
      const data = await response.json();
      setRecords(data);
      
      // Auto-extract facilities for editing lookups from loaded records
      const uniqueFacilities = [];
      const seen = new Set();
      data.forEach(r => {
        if (r.facility_detail && !seen.has(r.facility_detail.id)) {
          seen.add(r.facility_detail.id);
          uniqueFacilities.push(r.facility_detail);
        }
      });
      // Standard list fallback if empty
      if (uniqueFacilities.length === 0) {
        setFacilities([
          { id: 1, name: "San Francisco Corporate HQ", facility_code: "WERKS-1001" },
          { id: 2, name: "Frankfurt Production Plant", facility_code: "WERKS-1002" },
          { id: 3, name: "ConEd Meter Account #1042", facility_code: "CONED-4210" },
          { id: 4, name: "ConEd Meter Account #1043", facility_code: "MTR-9876" }
        ]);
      } else {
        setFacilities(uniqueFacilities);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecords();
  }, [filterScope, filterSource, filterStatus, filterAnomaly]);

  // File Upload Handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setUploadFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setUploadFile(e.target.files[0]);
    }
  };

  const executeUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('source_type', uploadSourceType);

    try {
      const response = await fetch(`${API_BASE}/api/ingestion/upload/`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to ingest file onto ESG platform.');
      }

      setUploadSuccess(`Ingested "${uploadFile.name}" successfully! Processed: ${data.processed_rows}, Failures: ${data.failed_rows}`);
      setUploadFile(null);
      fetchRecords(); // Refresh list immediately
    } catch (err) {
      console.error(err);
      setUploadError(err.message);
    } finally {
      setUploading(false);
    }
  };

  // Quick Action Handlers
  const handleApprove = async (e, recordId) => {
    e.stopPropagation(); // Avoid opening drawer
    try {
      const response = await fetch(`${API_BASE}/api/records/${recordId}/approve/`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Approval failed.');
      
      // Update local state instantly
      setRecords(prev => prev.map(r => r.id === recordId ? { ...r, status: 'APPROVED' } : r));
      
      // If currently open in drawer, update drawer state too
      if (activeDrawerRecord && activeDrawerRecord.id === recordId) {
        const updatedResponse = await fetch(`${API_BASE}/api/records/`);
        const updatedList = await updatedResponse.json();
        const freshRecord = updatedList.find(r => r.id === recordId);
        setActiveDrawerRecord(freshRecord);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const openRejectionDialog = (e, record) => {
    e.stopPropagation();
    setRejectingRecord(record);
    setRejectionReason('');
    setRejectionError(null);
  };

  const submitRejection = async () => {
    if (!rejectionReason.trim()) {
      setRejectionError("A rejection reason is mandatory.");
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/api/records/${rejectingRecord.id}/reject/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rejection_reason: rejectionReason })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Rejection failed.');

      setRecords(prev => prev.map(r => r.id === rejectingRecord.id ? { ...r, status: 'REJECTED', rejection_reason: rejectionReason } : r));
      
      if (activeDrawerRecord && activeDrawerRecord.id === rejectingRecord.id) {
        const updatedResponse = await fetch(`${API_BASE}/api/records/`);
        const updatedList = await updatedResponse.json();
        const freshRecord = updatedList.find(r => r.id === rejectingRecord.id);
        setActiveDrawerRecord(freshRecord);
      }

      setRejectingRecord(null);
    } catch (err) {
      setRejectionError(err.message);
    }
  };

  // Edit Handlers
  const startEdit = (e, record) => {
    e.stopPropagation();
    setEditingRecord(record);
    setEditQty(record.quantity);
    setEditFacilityId(record.facility ? record.facility : '');
    setEditError(null);
  };

  const submitEdit = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/records/${editingRecord.id}/edit/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quantity: editQty,
          facility_id: editFacilityId
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Manual override edit failed.');

      // Update state
      setRecords(prev => prev.map(r => r.id === editingRecord.id ? data : r));
      
      if (activeDrawerRecord && activeDrawerRecord.id === editingRecord.id) {
        setActiveDrawerRecord(data);
      }

      setEditingRecord(null);
    } catch (err) {
      setEditError(err.message);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', position: 'relative' }}>
      
      {/* 1. Ingestion File Upload Panel */}
      <div className="glass-panel" style={{ padding: '1.75rem' }}>
        <h2 style={{ margin: '0 0 1.25rem 0', fontSize: '1.25rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Upload size={18} style={{ color: '#10b981' }} /> Ingest Client Source File
        </h2>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Source Type Selector */}
          <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#9ca3af' }}>Select Source System:</span>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              {['SAP', 'UTILITY', 'TRAVEL'].map((type) => (
                <button
                  key={type}
                  onClick={() => setUploadSourceType(type)}
                  className={`nav-tab ${uploadSourceType === type ? 'active' : ''}`}
                  style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}
                >
                  {type === 'SAP' && 'SAP Fuel & Procurement'}
                  {type === 'UTILITY' && 'Utility Portal (Electricity)'}
                  {type === 'TRAVEL' && 'Corporate Travel Platform'}
                </button>
              ))}
            </div>
          </div>

          {/* Drag & Drop File Zone */}
          <div 
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current.click()}
            className={`dropzone ${dragActive ? 'active' : ''}`}
          >
            <input 
              ref={fileInputRef}
              type="file" 
              accept=".csv"
              onChange={handleFileChange}
              style={{ display: 'none' }} 
            />
            
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
              <FileText size={40} style={{ color: uploadFile ? '#10b981' : '#6b7280' }} />
              {uploadFile ? (
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#f3f4f6' }}>{uploadFile.name}</div>
                  <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>{(uploadFile.size / 1024).toFixed(1)} KB</div>
                </div>
              ) : (
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#f3f4f6' }}>Drag & drop your client export CSV here</div>
                  <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginTop: '0.25rem' }}>or click to browse local files</div>
                </div>
              )}
            </div>
          </div>

          {/* Upload Status Alerts */}
          {uploadError && (
            <div style={{ padding: '0.75rem 1rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px', color: '#f87171', fontSize: '0.85rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <AlertTriangle size={16} /> {uploadError}
            </div>
          )}

          {uploadSuccess && (
            <div style={{ padding: '0.75rem 1rem', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: '8px', color: '#34d399', fontSize: '0.85rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <Check size={16} /> {uploadSuccess}
            </div>
          )}

          {/* Submit Ingestion File Button */}
          {uploadFile && (
            <button 
              onClick={executeUpload}
              disabled={uploading}
              className="btn btn-primary"
              style={{ width: 'fit-content', alignSelf: 'flex-end' }}
            >
              {uploading ? (
                <> <RefreshCw size={14} style={{ animation: 'spin 1.5s linear infinite' }} /> Normalizing Ledger & Calculating Carbon... </>
              ) : (
                <> <Sparkles size={14} /> Execute Normalization Engine </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* 2. Filter Bar & Activity Ledger Header */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800 }}>Normalized Activity Records</h2>
            <p style={{ margin: '0.2rem 0 0 0', color: '#9ca3af', fontSize: '0.85rem' }}>Review ledger calculations, inspect source lineage, and sign off for audit.</p>
          </div>
          <button onClick={fetchRecords} className="btn btn-secondary">
            <RefreshCw size={14} /> Refresh Ledger
          </button>
        </div>

        {/* Filters Controls Box */}
        <div className="glass-panel" style={{ padding: '1rem', display: 'flex', flexWrap: 'wrap', gap: '1.25rem', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#9ca3af', fontSize: '0.85rem', fontWeight: 600 }}>
            <Filter size={16} /> Filters:
          </div>

          {/* Scope Filter */}
          <select 
            value={filterScope}
            onChange={(e) => setFilterScope(e.target.value)}
            className="input-field"
            style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
          >
            <option value="">All Scopes</option>
            <option value="1">Scope 1 - Direct Fuels</option>
            <option value="2">Scope 2 - Purchased Electricity</option>
            <option value="3">Scope 3 - Travel & Materials</option>
          </select>

          {/* Source Type Filter */}
          <select 
            value={filterSource}
            onChange={(e) => setFilterSource(e.target.value)}
            className="input-field"
            style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
          >
            <option value="">All Source Types</option>
            <option value="SAP">SAP Fuel & Procurement</option>
            <option value="UTILITY">Utility Electricity Statements</option>
            <option value="TRAVEL">Corporate Travel Bookings</option>
          </select>

          {/* Status Filter */}
          <select 
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="input-field"
            style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}
          >
            <option value="">All Review States</option>
            <option value="PENDING_REVIEW">Pending Review</option>
            <option value="APPROVED">Approved & Locked</option>
            <option value="REJECTED">Rejected</option>
          </select>

          {/* Anomalies Filter Checkbox */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', cursor: 'pointer', color: filterAnomaly ? '#fbbf24' : '#9ca3af', fontWeight: 500 }}>
            <input 
              type="checkbox"
              checked={filterAnomaly}
              onChange={(e) => setFilterAnomaly(e.target.checked)}
              style={{ cursor: 'pointer', accentColor: '#fbbf24' }}
            />
            Show Flagged Warnings Only
          </label>
        </div>
      </div>

      {/* 3. Normalized Records Grid Table */}
      <div className="table-container">
        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#9ca3af' }}>
            <RefreshCw size={24} style={{ animation: 'spin 2s linear infinite', color: '#10b981', margin: '0 auto 1rem auto' }} />
            Filtering ledger data...
          </div>
        ) : records.length === 0 ? (
          <div style={{ padding: '4rem 2rem', textAlign: 'center', color: '#9ca3af' }}>
            <FileText size={48} style={{ color: '#374151', marginBottom: '1rem' }} />
            <h4 style={{ margin: '0 0 0.5rem 0', color: '#f3f4f6' }}>No Activity Records Located</h4>
            <p style={{ margin: 0, fontSize: '0.85rem' }}>Select a source CSV file above and upload it to populate the carbon accounting ledger.</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Facility / Asset</th>
                <th>Original Inputs</th>
                <th>Normalized Qty</th>
                <th>Scope</th>
                <th>Calculated Footprint</th>
                <th>Flags</th>
                <th>Review Status</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => {
                const badgeClass = `badge badge-${r.source_type.toLowerCase()}`;
                const statusClass = `badge badge-${r.status.toLowerCase().replace('_', '')}`;
                const hasAnomalies = r.anomaly_flags && Object.keys(r.anomaly_flags).length > 0;

                return (
                  <tr 
                    key={r.id} 
                    onClick={() => setActiveDrawerRecord(r)}
                    style={{ cursor: 'pointer', transition: 'background var(--transition-fast)' }}
                  >
                    {/* Source */}
                    <td>
                      <span className={badgeClass}>{r.source_type}</span>
                    </td>
                    
                    {/* Facility */}
                    <td>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>
                        {r.facility_detail ? r.facility_detail.name : 'Corporate Operations (Unassigned)'}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.15rem' }}>
                        {r.facility_detail ? r.facility_detail.facility_code : 'Scope 3 Regional Log'}
                      </div>
                    </td>
                    
                    {/* Original Inputs */}
                    <td style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                      {parseFloat(r.original_quantity).toFixed(1)} {r.original_unit}
                    </td>

                    {/* Normalized Quantity */}
                    <td>
                      <span style={{ fontWeight: 500 }}>{parseFloat(r.quantity).toFixed(1)}</span>{' '}
                      <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>{r.unit}</span>
                    </td>

                    {/* Scope */}
                    <td>
                      <span style={{ 
                        padding: '0.2rem 0.5rem', 
                        borderRadius: '4px', 
                        fontSize: '0.7rem', 
                        fontWeight: 700,
                        background: r.scope === 1 ? 'rgba(245,158,11,0.1)' : r.scope === 2 ? 'rgba(59,130,246,0.1)' : 'rgba(139,92,246,0.1)',
                        color: r.scope === 1 ? '#fbbf24' : r.scope === 2 ? '#60a5fa' : '#a78bfa',
                        border: r.scope === 1 ? '1px solid rgba(245,158,11,0.2)' : r.scope === 2 ? '1px solid rgba(59,130,246,0.2)' : '1px solid rgba(139,92,246,0.2)'
                      }}>
                        Scope {r.scope}
                      </span>
                    </td>

                    {/* Calculated Footprint */}
                    <td>
                      <span style={{ fontWeight: 800, color: '#f3f4f6' }}>{parseFloat(r.co2e_emissions).toFixed(3)}</span>{' '}
                      <span style={{ fontSize: '0.75rem', color: '#9ca3af', fontWeight: 600 }}>t CO₂e</span>
                    </td>

                    {/* Warnings/Flags */}
                    <td>
                      {hasAnomalies ? (
                        <div style={{ display: 'flex', color: '#fbbf24', gap: '0.25rem', alignItems: 'center' }}>
                          <AlertTriangle size={14} />
                          <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>
                            {Object.keys(r.anomaly_flags).join(', ')}
                          </span>
                        </div>
                      ) : (
                        <span style={{ color: '#4b5563', fontSize: '0.75rem' }}>—</span>
                      )}
                    </td>

                    {/* Status */}
                    <td>
                      <span className={statusClass}>
                        {r.status === 'PENDING_REVIEW' && 'Pending Review'}
                        {r.status === 'APPROVED' && 'Approved'}
                        {r.status === 'REJECTED' && 'Rejected'}
                      </span>
                    </td>

                    {/* Actions */}
                    <td onClick={(e) => e.stopPropagation()} style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end', alignItems: 'center' }}>
                        {r.status !== 'APPROVED' ? (
                          <>
                            {/* Manual Override Button */}
                            <button 
                              onClick={(e) => startEdit(e, r)}
                              className="btn btn-secondary" 
                              style={{ padding: '0.35rem 0.6rem', fontSize: '0.75rem' }}
                              title="Override values"
                            >
                              <Edit3 size={12} /> Override
                            </button>
                            
                            {/* Approve Button */}
                            <button 
                              onClick={(e) => handleApprove(e, r.id)}
                              className="btn btn-primary"
                              style={{ padding: '0.35rem 0.6rem', fontSize: '0.75rem', background: '#10b981', color: '#ffffff' }}
                              title="Sign off row"
                            >
                              <Check size={12} /> Approve
                            </button>

                            {/* Reject Button */}
                            <button 
                              onClick={(e) => openRejectionDialog(e, r)}
                              className="btn btn-danger"
                              style={{ padding: '0.35rem 0.6rem', fontSize: '0.75rem' }}
                              title="Flag as Rejected"
                            >
                              <X size={12} />
                            </button>
                          </>
                        ) : (
                          <div style={{ fontSize: '0.75rem', color: '#6b7280', display: 'flex', alignItems: 'center', gap: '0.25rem', fontWeight: 600 }}>
                            <Check size={12} style={{ color: '#10b981' }} /> Locked
                          </div>
                        )}
                        <ChevronRight size={16} style={{ color: '#4b5563' }} />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* 4. Slide-over Lineage Inspector Panel Drawer */}
      <div className={`drawer ${activeDrawerRecord ? 'open' : ''}`}>
        {activeDrawerRecord && (
          <>
            <div className="drawer-header">
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800 }}>Audit Lineage Inspector</h3>
                <p style={{ margin: '0.15rem 0 0 0', color: '#9ca3af', fontSize: '0.75rem' }}>Row Lineage & Historic Audit Ledger</p>
              </div>
              <button 
                onClick={() => setActiveDrawerRecord(null)}
                className="btn btn-secondary"
                style={{ padding: '0.4rem', borderRadius: '50%' }}
              >
                <X size={16} />
              </button>
            </div>

            <div className="drawer-body" style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
              {/* Scope & Emissions Card */}
              <div className="glass-panel" style={{ padding: '1.25rem', background: 'rgba(255,255,255,0.015)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <span className={`badge badge-${activeDrawerRecord.source_type.toLowerCase()}`}>{activeDrawerRecord.source_type}</span>
                  <span style={{ fontSize: '0.8rem', color: '#9ca3af', fontWeight: 600 }}>Scope {activeDrawerRecord.scope}</span>
                </div>
                <h2 style={{ margin: '0 0 0.25rem 0', fontSize: '1.8rem', fontWeight: 800, color: '#f3f4f6' }}>
                  {parseFloat(activeDrawerRecord.co2e_emissions).toFixed(4)} <span style={{ fontSize: '0.95rem', fontWeight: 'normal', color: '#9ca3af' }}>t CO₂e</span>
                </h2>
                <div style={{ fontSize: '0.8rem', color: '#9ca3af', display: 'flex', flexDirection: 'column', gap: '0.25rem', marginTop: '0.75rem' }}>
                  <div><strong>Standard factor:</strong> {activeDrawerRecord.emission_factor_used} kg CO₂e / {activeDrawerRecord.unit}</div>
                  {activeDrawerRecord.facility_detail && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', marginTop: '0.25rem' }}>
                      <MapPin size={12} style={{ color: '#10b981' }} /> {activeDrawerRecord.facility_detail.name} ({activeDrawerRecord.facility_detail.region})
                    </div>
                  )}
                </div>
              </div>

              {/* Verbatim Source Lineage JSON */}
              <div>
                <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Verbatim Source Row (Audit Lineage)
                </h4>
                <div style={{ background: '#0b0f19', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem', overflowX: 'auto' }}>
                  <pre style={{ margin: 0, fontSize: '0.75rem', fontFamily: 'monospace', color: '#34d399', lineHeight: 1.4 }}>
                    {JSON.stringify(activeDrawerRecord.raw_record_detail ? activeDrawerRecord.raw_record_detail.raw_payload : { "info": "Manual ledger entry" }, null, 2)}
                  </pre>
                </div>
              </div>

              {/* Vertical Audit Trail Logs */}
              <div>
                <h4 style={{ margin: '0 0 1rem 0', fontSize: '0.85rem', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <History size={14} /> Chronological Audit Ledger
                </h4>
                
                {activeDrawerRecord.audit_trail && activeDrawerRecord.audit_trail.length === 0 ? (
                  <p style={{ fontSize: '0.8rem', color: '#6b7280' }}>No manual interventions recorded for this entry.</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', borderLeft: '2px solid #1f2937', paddingLeft: '1rem', marginLeft: '0.5rem' }}>
                    {activeDrawerRecord.audit_trail.map((log) => (
                      <div key={log.id} style={{ position: 'relative', fontSize: '0.8rem' }}>
                        {/* Dot on timeline */}
                        <div style={{ position: 'absolute', width: '8px', height: '8px', background: '#10b981', borderRadius: '50%', left: '-1.3rem', top: '0.3rem', border: '2px solid #0f1624' }}></div>
                        
                        <div style={{ fontWeight: 600, color: '#f3f4f6', display: 'flex', justifyContent: 'space-between' }}>
                          <span>{log.action}</span>
                          <span style={{ fontSize: '0.7rem', color: '#6b7280' }}>
                            {new Date(log.timestamp).toLocaleString()}
                          </span>
                        </div>
                        
                        <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.15rem' }}>
                          {log.changes.message ? (
                            <div>{log.changes.message}</div>
                          ) : (
                            <div style={{ background: 'rgba(0,0,0,0.15)', padding: '0.35rem', borderRadius: '4px', marginTop: '0.25rem', fontFamily: 'monospace' }}>
                              {JSON.stringify(log.changes)}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {/* 5. In-place Manual Override Modal Popover */}
      {editingRecord && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0, 0, 0, 0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100, backdropFilter: 'blur(4px)' }}>
          <div className="glass-panel" style={{ padding: '2rem', width: '420px', maxWidth: '90vw' }}>
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.2rem', fontWeight: 800 }}>Override Normalized Inputs</h3>
            <p style={{ color: '#9ca3af', fontSize: '0.8rem', marginTop: '-0.5rem', marginBottom: '1.5rem' }}>
              Override values. Carbon calculations and CO₂e footprint will be recalculated instantly.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
              {/* Quantity Input */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af' }}>Normalized Quantity ({editingRecord.unit}):</label>
                <input 
                  type="number"
                  value={editQty}
                  onChange={(e) => setEditQty(e.target.value)}
                  className="input-field" 
                />
              </div>

              {/* Facility Mapping Override */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af' }}>Facility Assignment Mapping:</label>
                <select
                  value={editFacilityId}
                  onChange={(e) => setEditFacilityId(e.target.value)}
                  className="input-field"
                >
                  <option value="">Corporate Operations (Unassigned)</option>
                  {facilities.map((fac) => (
                    <option key={fac.id} value={fac.id}>
                      {fac.name} ({fac.facility_code})
                    </option>
                  ))}
                </select>
              </div>

              {editError && (
                <div style={{ fontSize: '0.8rem', color: '#ef4444' }}>{editError}</div>
              )}
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button onClick={() => setEditingRecord(null)} className="btn btn-secondary">Cancel</button>
              <button onClick={submitEdit} className="btn btn-primary">Apply Changes</button>
            </div>
          </div>
        </div>
      )}

      {/* 6. Rejection Dialog Modal */}
      {rejectingRecord && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0, 0, 0, 0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100, backdropFilter: 'blur(4px)' }}>
          <div className="glass-panel" style={{ padding: '2rem', width: '400px', maxWidth: '90vw' }}>
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.2rem', fontWeight: 800, color: '#ef4444' }}>Reject Activity Record</h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#9ca3af' }}>Reason for Rejection (Audit Compliant):</label>
                <textarea 
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="input-field" 
                  rows={4}
                  placeholder="Explain why this row is rejected (e.g. billing date overlap, incorrect meter readings)..."
                  style={{ resize: 'none', fontFamily: 'inherit' }}
                />
              </div>
              
              {rejectionError && (
                <div style={{ fontSize: '0.8rem', color: '#ef4444' }}>{rejectionError}</div>
              )}
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button onClick={() => setRejectingRecord(null)} className="btn btn-secondary">Cancel</button>
              <button onClick={submitRejection} className="btn btn-danger">Flag & Reject</button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

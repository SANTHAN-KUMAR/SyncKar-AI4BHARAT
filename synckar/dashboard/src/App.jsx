import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import './index.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

// All 20 UBIDs with business names
const UBID_LIST = [
  { ubid: 'KA-TEST-0001', name: 'Bengaluru Silk Weavers Pvt Ltd' },
  { ubid: 'KA-TEST-0002', name: 'Mysuru Agro Industries Ltd' },
  { ubid: 'KA-TEST-0003', name: 'Hubli Steel Fabricators Pvt Ltd' },
  { ubid: 'KA-TEST-0004', name: 'Mangaluru Cashew Exports Ltd' },
  { ubid: 'KA-TEST-0005', name: 'Dharwad Pharma Solutions Pvt Ltd' },
  { ubid: 'KA-TEST-0006', name: 'Belagavi Textile Mills Ltd' },
  { ubid: 'KA-TEST-0007', name: 'Tumkur Auto Components Pvt Ltd' },
  { ubid: 'KA-TEST-0008', name: 'Shivamogga Paper Industries Ltd' },
  { ubid: 'KA-TEST-0009', name: 'Kolar Gold Jewellers Pvt Ltd' },
  { ubid: 'KA-TEST-0010', name: 'Raichur Power Equipment Ltd' },
  { ubid: 'KA-TEST-0011', name: 'Bidar Ceramics Pvt Ltd' },
  { ubid: 'KA-TEST-0012', name: 'Vijayapura Sugar Mills Ltd' },
  { ubid: 'KA-TEST-0013', name: 'Gadag Granite Exports Pvt Ltd' },
  { ubid: 'KA-TEST-0014', name: 'Koppal Iron & Steel Ltd' },
  { ubid: 'KA-TEST-0015', name: 'Yadgir Cement Works Pvt Ltd' },
  { ubid: 'KA-TEST-0016', name: 'Bengaluru IT Solutions Pvt Ltd' },
  { ubid: 'KA-TEST-0017', name: 'Mysuru Handicrafts Emporium' },
  { ubid: 'KA-TEST-0018', name: 'Mangaluru Seafood Processors Ltd' },
  { ubid: 'KA-TEST-0019', name: 'Bengaluru Fintech Ventures Pvt Ltd' },
  { ubid: 'KA-TEST-0020', name: 'Karnataka Organic Farms Ltd' },
]

function App() {
  const [page, setPage] = useState('overview')
  const [stats, setStats] = useState(null)
  const [audit, setAudit] = useState([])
  const [conflicts, setConflicts] = useState([])
  const [dlq, setDlq] = useState([])
  const [searchUbid, setSearchUbid] = useState('')
  const [verifyResult, setVerifyResult] = useState(null)
  const [health, setHealth] = useState(null)

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stats`)
      const data = await res.json()
      setStats(data)
    } catch (e) { console.error('Stats fetch failed:', e) }
  }, [])

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`)
      const data = await res.json()
      setHealth(data)
    } catch (e) { console.error('Health fetch failed:', e) }
  }, [])

  const fetchAudit = useCallback(async (ubid = '') => {
    try {
      const params = ubid ? `?ubid=${ubid}` : '?limit=50'
      const res = await fetch(`${API_BASE}/api/audit${params}`)
      const data = await res.json()
      setAudit(data.audit_entries || [])
    } catch (e) { console.error('Audit fetch failed:', e) }
  }, [])

  const fetchConflicts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dlq/conflicts`)
      const data = await res.json()
      setConflicts(data.conflicts || [])
    } catch (e) { console.error('Conflicts fetch failed:', e) }
  }, [])

  const fetchDlq = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dlq`)
      const data = await res.json()
      setDlq(data.dlq_items || [])
    } catch (e) { console.error('DLQ fetch failed:', e) }
  }, [])

  const verifyAudit = async (auditId) => {
    try {
      const res = await fetch(`${API_BASE}/api/audit/verify/${auditId}`)
      const data = await res.json()
      setVerifyResult(data)
    } catch (e) { console.error('Verify failed:', e) }
  }

  // Auto-refresh stats every 3s so the overview updates live during demos
  useEffect(() => {
    fetchStats()
    fetchHealth()
    const interval = setInterval(() => {
      fetchStats()
      fetchHealth()
    }, 3000)
    return () => clearInterval(interval)
  }, [fetchStats, fetchHealth])

  useEffect(() => {
    if (page === 'audit') fetchAudit(searchUbid)
    if (page === 'conflicts') fetchConflicts()
    if (page === 'dlq') fetchDlq()
  }, [page, fetchAudit, fetchConflicts, fetchDlq, searchUbid])

  // Auto-refresh audit/conflicts when on those pages during demo
  useEffect(() => {
    if (page !== 'audit' && page !== 'conflicts') return
    const interval = setInterval(() => {
      if (page === 'audit') fetchAudit(searchUbid)
      if (page === 'conflicts') fetchConflicts()
    }, 4000)
    return () => clearInterval(interval)
  }, [page, fetchAudit, fetchConflicts, searchUbid])

  const pages = [
    { id: 'overview', label: 'Overview' },
    { id: 'mock', label: 'Data Flow Demo' },
    { id: 'audit', label: 'Audit Trail' },
    { id: 'conflicts', label: 'Conflicts' },
    { id: 'dlq', label: 'DLQ' },
    { id: 'verify', label: 'BSA Verify' }
  ]

  return (
    <div className="app">
      <header className="header">
        <div className="header-logo">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
          </svg>
          <h1>SyncKar</h1>
          <span className="badge">Command Center</span>
        </div>
        <nav className="nav">
          {pages.map(p => (
            <button
              key={p.id}
              className={`nav-btn ${page === p.id ? 'active' : ''}`}
              onClick={() => setPage(p.id)}
            >
              {p.label}
            </button>
          ))}
          <Link to="/portal" className="nav-btn-portals">
            Portals
          </Link>
        </nav>
      </header>

      <main className="main">
        {page === 'overview'  && <OverviewPage stats={stats} health={health} />}
        {page === 'mock'      && <MockSystemsPage />}
        {page === 'audit'     && (
          <AuditPage
            audit={audit}
            searchUbid={searchUbid}
            onSearch={setSearchUbid}
            onFetch={() => fetchAudit(searchUbid)}
          />
        )}
        {page === 'conflicts' && <ConflictsPage conflicts={conflicts} onRefresh={fetchConflicts} />}
        {page === 'dlq'       && <DLQPage dlq={dlq} />}
        {page === 'verify'    && (
          <VerifyPage
            audit={audit}
            verifyResult={verifyResult}
            onVerify={verifyAudit}
            onFetchAudit={() => fetchAudit('')}
          />
        )}
      </main>
    </div>
  )
}

// ─── Overview ────────────────────────────────────────────────────────────────

function OverviewPage({ stats, health }) {
  return (
    <>
      <div className="stats-grid">
        <div className="stat-card blue">
          <div className="stat-label">Total Propagations</div>
          <div className="stat-value">{stats?.audit_entries ?? '—'}</div>
        </div>
        <div className="stat-card amber">
          <div className="stat-label">Conflicts Detected</div>
          <div className="stat-value">{stats?.conflicts_detected ?? '—'}</div>
        </div>
        <div className="stat-card red">
          <div className="stat-label">DLQ Depth</div>
          <div className="stat-value">{stats?.dlq_depth ?? '—'}</div>
        </div>
        <div className="stat-card purple">
          <div className="stat-label">Outbox Pending</div>
          <div className="stat-value">{stats?.outbox_pending ?? '—'}</div>
        </div>
        <div className="stat-card green">
          <div className="stat-label">Conflict Records</div>
          <div className="stat-value">{stats?.conflict_records ?? '—'}</div>
        </div>
      </div>

      <div className="table-container">
        <div className="table-header">
          <h2>System Health</h2>
          <span className={health?.status === 'healthy' ? 'badge-success' : 'badge-error'}>
            {health?.status ?? 'UNKNOWN'}
          </span>
        </div>
        <table>
          <thead>
            <tr><th>Service Node</th><th>Status Code</th></tr>
          </thead>
          <tbody>
            {health?.checks && Object.entries(health.checks).map(([svc, status]) => (
              <tr key={svc}>
                <td style={{ textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>{svc}</td>
                <td>
                  <span className={status === 'healthy' ? 'badge-success' : 'badge-error'}>
                    {status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

// ─── Mock Systems (Narrative View) ───────────────────────────────────────────

const SYSTEM_LABELS = {
  sws:       { label: 'Single Window',   icon: <rect width="18" height="18" x="3" y="3" rx="2" ry="2"/> },
  shop:      { label: 'Shop Est.',       icon: <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/> },
  factories: { label: 'Factories Dept.', icon: <path d="M2 20h20M4 20V4l8 6 8-6v16"/> },
}

const EDITABLE_FIELDS = {
  sws: [
    { key: 'registered_address', label: 'Registered Address', type: 'text' },
    { key: 'authorized_signatory', label: 'Authorized Signatory', type: 'text' },
    { key: 'primary_contact', label: 'Primary Contact', type: 'text' },
    { key: 'employee_headcount', label: 'Employee Headcount', type: 'number' },
    { key: 'operational_status', label: 'Operational Status', type: 'select',
      options: ['active', 'inactive', 'suspended'] },
  ],
  shop: [
    { key: 'Buss_Addr_Line1', label: 'Business Address', type: 'text' },
    { key: 'Auth_Sign_Name', label: 'Authorized Signatory', type: 'text' },
    { key: 'Contact_Phone', label: 'Contact Phone', type: 'text' },
    { key: 'Emp_Count', label: 'Employee Count', type: 'number' },
    { key: 'Op_Status', label: 'Operational Status', type: 'select',
      options: ['active', 'inactive', 'suspended'] },
  ],
  factories: [
    { key: 'factory_address', label: 'Factory Address', type: 'text' },
    { key: 'signatory_name', label: 'Signatory Name', type: 'text' },
    { key: 'contact_number', label: 'Contact Number', type: 'text' },
    { key: 'worker_count', label: 'Worker Count', type: 'number' },
    { key: 'factory_status', label: 'Factory Status', type: 'select',
      options: ['active', 'inactive', 'suspended'] },
  ],
}

function MockSystemsPage() {
  const [selectedUbid, setSelectedUbid] = useState('KA-TEST-0001')
  const [records, setRecords] = useState({ sws: null, shop: null, factories: null })
  const [loading, setLoading] = useState({})
  const [saving, setSaving] = useState({})
  const [seeding, setSeeding] = useState(false)
  const [edits, setEdits] = useState({})
  const [toast, setToast] = useState(null)
  const toastTimer = useRef(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(null), 4000)
  }

  const fetchRecord = useCallback(async (system, ubid) => {
    setLoading(l => ({ ...l, [system]: true }))
    try {
      const res = await fetch(`${API_BASE}/api/mock/${system}/record/${ubid}`)
      if (!res.ok) throw new Error(`${res.status}`)
      const data = await res.json()
      setRecords(r => ({ ...r, [system]: data }))
      const fields = EDITABLE_FIELDS[system] || []
      const initial = {}
      fields.forEach(f => { initial[f.key] = data[f.key] ?? '' })
      setEdits(e => ({ ...e, [system]: initial }))
    } catch (err) {
      setRecords(r => ({ ...r, [system]: null }))
    } finally {
      setLoading(l => ({ ...l, [system]: false }))
    }
  }, [])

  const refreshAll = useCallback((ubid) => {
    fetchRecord('sws', ubid)
    fetchRecord('shop', ubid)
    fetchRecord('factories', ubid)
  }, [fetchRecord])

  useEffect(() => {
    setRecords({ sws: null, shop: null, factories: null })
    setEdits({})
    refreshAll(selectedUbid)
  }, [selectedUbid, refreshAll])

  const handleEdit = (system, key, value) => {
    setEdits(e => ({ ...e, [system]: { ...e[system], [key]: value } }))
  }

  const handleSave = async (system) => {
    setSaving(s => ({ ...s, [system]: true }))
    try {
      const body = edits[system] || {}
      const res = await fetch(`${API_BASE}/api/mock/${system}/record/${selectedUbid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`${res.status}`)
      showToast(`${SYSTEM_LABELS[system].label} Updated — SyncKar tracking event`, 'info')
      await fetchRecord(system, selectedUbid)
    } catch (err) {
      showToast(`Update Failed ${SYSTEM_LABELS[system].label}: ${err.message}`, 'error')
    } finally {
      setSaving(s => ({ ...s, [system]: false }))
    }
  }

  const handleConflict = async () => {
    const swsBody = { registered_address: `${Date.now()} SWS Street, Bangalore 560001` }
    const factBody = { factory_address: `${Date.now()} Factory Lane, Bangalore 560002` }
    showToast('Triggering simultaneous conflict update…', 'info')

    const [swsRes, factRes] = await Promise.all([
      fetch(`${API_BASE}/api/mock/sws/record/${selectedUbid}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(swsBody),
      }),
      fetch(`${API_BASE}/api/mock/factories/record/${selectedUbid}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(factBody),
      }),
    ])

    if (!swsRes.ok || !factRes.ok) {
      const code = !swsRes.ok ? swsRes.status : factRes.status
      showToast(`Conflict trigger failed (${code})`, 'error')
      return
    }

    showToast('Conflict submitted — applying SWS_WINS resolution', 'success')
    refreshAll(selectedUbid)
  }

  const handleSeed = async () => {
    setSeeding(true)
    try {
      const res = await fetch(`${API_BASE}/api/mock/seed`, { method: 'POST' })
      if (!res.ok) throw new Error(`${res.status}`)
      const data = await res.json()
      showToast(`Data seeded (SWS:${data.seeded?.sws} SHOP:${data.seeded?.shop})`, 'success')
      refreshAll(selectedUbid)
    } catch (err) {
      showToast(`Seed failed: ${err.message}`, 'error')
    } finally {
      setSeeding(false)
    }
  }

  const handleReset = async () => {
    setSeeding(true)
    try {
      const res = await fetch(`${API_BASE}/api/mock/reset`, { method: 'POST' })
      if (!res.ok) throw new Error(`${res.status}`)
      const data = await res.json()
      showToast(`Database Reset`, 'success')
      refreshAll(selectedUbid)
    } catch (err) {
      showToast(`Reset failed: ${err.message}`, 'error')
    } finally {
      setSeeding(false)
    }
  }

  const handleScenarioA = async () => {
    const body = { registered_address: `${Date.now()} Scenario-A Street, Bengaluru 560001` }
    showToast('Scenario A: updating SWS...', 'info')
    try {
      const res = await fetch(`${API_BASE}/api/mock/sws/record/${selectedUbid}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`${res.status} — seed data first`)
      showToast('Scenario A triggered — SWS updated', 'success')
      fetchRecord('sws', selectedUbid)
    } catch (err) {
      showToast(`Scenario A failed: ${err.message}`, 'error')
    }
  }

  const handleScenarioB = async () => {
    const body = { Buss_Addr_Line1: `${Date.now()} Scenario-B Road, Bengaluru 560002` }
    showToast('Scenario B: updating Shop...', 'info')
    try {
      const res = await fetch(`${API_BASE}/api/mock/shop/record/${selectedUbid}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`${res.status} — seed data first`)
      showToast('Scenario B triggered — Shop updated', 'success')
      fetchRecord('shop', selectedUbid)
    } catch (err) {
      showToast(`Scenario B failed: ${err.message}`, 'error')
    }
  }

  const renderPanel = (system, customClass) => {
    const { label, icon } = SYSTEM_LABELS[system]
    const record = records[system]
    const fields = EDITABLE_FIELDS[system] || []
    const isLoading = loading[system]
    const isSaving = saving[system]
    const edit = edits[system] || {}

    return (
      <div className={`mock-panel ${customClass}`}>
        <div className="mock-panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {icon}
            </svg>
            <span className="mock-panel-title">{label}</span>
          </div>
          <span className="badge-info">{selectedUbid}</span>
        </div>

        {isLoading ? (
          <div className="mock-loading">Loading Object...</div>
        ) : !record ? (
          <div className="mock-empty">No Entity</div>
        ) : (
          <>
            <div className="mock-readonly">
              <div className="mock-field-row">
                <span className="mock-field-label">Entity Name</span>
                <span className="mock-field-value">{record.business_name}</span>
              </div>
            </div>

            <div className="mock-fields">
              {fields.map(f => (
                <div key={f.key} className="mock-field-row">
                  <label className="mock-field-label">{f.label}</label>
                  {f.type === 'select' ? (
                    <select
                      className="mock-input"
                      value={edit[f.key] ?? ''}
                      onChange={e => handleEdit(system, f.key, e.target.value)}
                    >
                      {f.options.map(o => <option key={o} value={o}>{o.toUpperCase()}</option>)}
                    </select>
                  ) : (
                    <input
                      className="mock-input"
                      type={f.type}
                      value={edit[f.key] ?? ''}
                      onChange={e => handleEdit(system, f.key,
                        f.type === 'number' ? Number(e.target.value) : e.target.value)}
                    />
                  )}
                </div>
              ))}
            </div>

            <div className="mock-panel-footer">
              <span className="mock-modified animate-update" key={record.last_modified}>
                {record.last_modified?.slice(11, 19) ?? '--:--:--'}
              </span>
              <button
                className={`btn btn-primary btn-sm ${isSaving ? 'btn-saving' : ''}`}
                onClick={() => handleSave(system)}
                disabled={isSaving}
              >
                {isSaving ? 'EXECUTING' : `WRITE TO ${system.toUpperCase()}`}
              </button>
            </div>
          </>
        )}
      </div>
    )
  }

  return (
    <div>
      {toast && (
        <div className={`toast toast-${toast.type}`}>{toast.msg}</div>
      )}

      <div className="mock-controls">
        <div className="mock-controls-left">
          <span className="mock-label">Target ID</span>
          <select
            className="mock-select"
            value={selectedUbid}
            onChange={e => setSelectedUbid(e.target.value)}
          >
            {UBID_LIST.map(u => (
              <option key={u.ubid} value={u.ubid}>{u.ubid} | {u.name}</option>
            ))}
          </select>
        </div>
        <div className="mock-controls-right">
          <button className="btn btn-seed" onClick={handleSeed} disabled={seeding}>
            [SEED DB]
          </button>
          <button className="btn btn-reset" onClick={handleReset} disabled={seeding}>
            [RESET]
          </button>
          <button className="btn btn-scenario-a" onClick={handleScenarioA}>
            RUN A: SWS &rarr; DEPT
          </button>
          <button className="btn btn-scenario-b" onClick={handleScenarioB}>
            RUN B: DEPT &rarr; SWS
          </button>
          <button className="btn btn-conflict" onClick={handleConflict}>
            TRIGGER CONFLICT
          </button>
        </div>
      </div>
      
      <div className="mock-hint-row">
        <span className="mock-hint">Event A: SWS updates, propagates to Shop & Factories</span>
        <span className="mock-hint">Event B: Shop updates, propagates to SWS</span>
        <span className="mock-hint">Event C: Conflict via simultaneous edits</span>
      </div>

      <div className="architecture-container">
        {/* Source Side */}
        <div className="architecture-side">
          {renderPanel('sws', 'mock-panel-sws')}
        </div>
        
        {/* SyncKar Middle Layer Indicator */}
        <div className="architecture-center">
          <div>DATA BUS</div>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" strokeWidth="2">
            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
          </svg>
          <div style={{ marginTop: 8 }}>SYNCKAR</div>
        </div>

        {/* Target Side */}
        <div className="architecture-side">
          {renderPanel('shop', 'mock-panel-dept')}
          {renderPanel('factories', 'mock-panel-dept')}
        </div>
      </div>

      <div className="mock-tip">
        <strong>NOTE:</strong> Monitor the <em>Audit Trail</em> or <em>Conflicts</em> tab to view raw system ledger entries generated by SyncKar after a mutation.
      </div>
    </div>
  )
}

// ─── Audit ────────────────────────────────────────────────────────────────────

function AuditPage({ audit, searchUbid, onSearch, onFetch }) {
  return (
    <div className="table-container">
      <div className="table-header">
        <h2>Ledger ({audit.length})</h2>
        <div style={{ display: 'flex', gap: 16 }}>
          <input
            className="search-input"
            placeholder="[UBID] e.g. KA-TEST-0001"
            value={searchUbid}
            onChange={e => onSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && onFetch()}
          />
          <button className="btn btn-primary" onClick={onFetch}>Query</button>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Target ID</th>
            <th>Property</th>
            <th>Vector</th>
            <th>Payload</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {audit.map((row, i) => (
            <tr key={i}>
              <td style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>
                {row.created_at?.slice(0, 19)}
              </td>
              <td><span className="badge-info">{row.ubid}</span></td>
              <td>{row.field_modified}</td>
              <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                {row.source_system} &rarr; {row.target_system}
              </td>
              <td style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                {row.new_value?.slice(0, 40)}
              </td>
              <td>
                {row.conflict_detected ? (
                  <span className="badge-warning">{row.resolution_policy || 'CONFLICT'}</span>
                ) : (
                  <span className="badge-success">OK</span>
                )}
              </td>
            </tr>
          ))}
          {audit.length === 0 && (
            <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 48, fontFamily: 'var(--font-mono)' }}>
              Awaiting Events.
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ─── Conflicts ────────────────────────────────────────────────────────────────

function ConflictsPage({ conflicts, onRefresh }) {
  return (
    <div className="table-container">
      <div className="table-header">
        <h2>Conflict Log ({conflicts.length})</h2>
        <button className="btn btn-primary btn-sm" onClick={onRefresh}>Sync</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Target ID</th>
            <th>Property</th>
            <th>Rule</th>
            <th>Accepted Vector</th>
            <th>Rejected Vector</th>
            <th>Conf</th>
          </tr>
        </thead>
        <tbody>
          {conflicts.map((c, i) => (
            <tr key={i}>
              <td style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>{c.created_at?.slice(0, 19)}</td>
              <td><span className="badge-info">{c.ubid}</span></td>
              <td>{c.field}</td>
              <td><span className="badge-warning">{c.policy_applied}</span></td>
              <td style={{ color: 'var(--accent-green)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{c.winning_value?.slice(0, 30)}</td>
              <td style={{ color: 'var(--text-secondary)', textDecoration: 'line-through', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{c.losing_value?.slice(0, 30)}</td>
              <td>
                <span className={
                  c.temporal_confidence === 'HIGH' ? 'badge-success' :
                  c.temporal_confidence === 'MEDIUM' ? 'badge-warning' : 'badge-error'
                }>
                  {c.temporal_confidence}
                </span>
              </td>
            </tr>
          ))}
          {conflicts.length === 0 && (
            <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 48, fontFamily: 'var(--font-mono)' }}>
              No recorded conflicts.
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ─── DLQ ─────────────────────────────────────────────────────────────────────

function DLQPage({ dlq }) {
  return (
    <div className="table-container">
      <div className="table-header">
        <h2>Dead Letter Queue ({dlq.length})</h2>
      </div>
      <table>
        <thead>
          <tr>
            <th>Timestamp</th><th>Target ID</th><th>Origin</th>
            <th>Exception</th><th>State</th><th>Action</th>
          </tr>
        </thead>
        <tbody>
          {dlq.map((item, i) => (
            <tr key={i}>
              <td style={{ fontSize: 10, fontFamily: 'var(--font-mono)' }}>{item.created_at?.slice(0, 19)}</td>
              <td><span className="badge-info">{item.ubid}</span></td>
              <td>{item.source_system}</td>
              <td style={{ maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{item.error_reason}</td>
              <td><span className="badge-error">{item.status}</span></td>
              <td><button className="btn btn-primary btn-sm">RETRY</button></td>
            </tr>
          ))}
          {dlq.length === 0 && (
            <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 48, fontFamily: 'var(--font-mono)' }}>
              Queue Empty.
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ─── Verify ───────────────────────────────────────────────────────────────────

function VerifyPage({ audit, verifyResult, onVerify, onFetchAudit }) {
  useEffect(() => { onFetchAudit() }, [onFetchAudit])

  return (
    <div>
      <div className="table-container">
        <div className="table-header">
          <h2>BSA 2023 Verification</h2>
        </div>
        <table>
          <thead>
            <tr>
              <th>Trace ID</th><th>Target ID</th><th>Property</th>
              <th>Vector</th><th>Action</th>
            </tr>
          </thead>
          <tbody>
            {audit.slice(0, 10).map((row, i) => (
              <tr key={i}>
                <td style={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}>{row.audit_id?.slice(0, 8)}…</td>
                <td><span className="badge-info">{row.ubid}</span></td>
                <td>{row.field_modified}</td>
                <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>{row.source_system} &rarr; {row.target_system}</td>
                <td>
                  <button className="btn btn-primary btn-sm" onClick={() => onVerify(row.audit_id)}>
                    VALIDATE
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {verifyResult && (
        <div className="verify-card">
          <h3 style={{ marginBottom: 24, fontFamily: 'var(--font-display)', textTransform: 'uppercase' }}>Integrity Check</h3>
          <div className={`verify-result ${verifyResult.signature_valid ? 'valid' : 'invalid'}`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 24, marginBottom: 16 }}>
              {verifyResult.signature_valid ? (
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--accent-green)" strokeWidth="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
              ) : (
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--accent-red)" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="15" y1="9" x2="9" y2="15"></line>
                  <line x1="9" y1="9" x2="15" y2="15"></line>
                </svg>
              )}
              <div>
                <div style={{ fontSize: 20, fontFamily: 'var(--font-display)', fontWeight: 700, color: verifyResult.signature_valid ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                  {verifyResult.signature_valid ? 'SIGNATURE VALID' : 'TAMPER DETECTED'}
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>
                  BSA_2023_COMPLIANT: {verifyResult.bsa_2023_compliant ? 'TRUE' : 'FALSE'}
                </div>
              </div>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', borderTop: '1px solid var(--border)', paddingTop: 16, display: 'grid', gap: 8 }}>
              <div>AUDIT_ID: {verifyResult.audit_id}</div>
              <div>SHA256_HASH: {verifyResult.payload_sha256}</div>
              <div>TARGET_ID: {verifyResult.verification_details?.ubid}</div>
              <div>PROPERTY: {verifyResult.verification_details?.field}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App

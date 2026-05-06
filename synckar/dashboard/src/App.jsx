import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import './index.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

// All 20 UBIDs with business names — matches the full seeded dataset
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

  const pages = ['overview', 'mock', 'audit', 'conflicts', 'dlq', 'verify']

  return (
    <div className="app">
      <header className="header">
        <div className="header-logo">
          <h1>⚡ SyncKar</h1>
          <span className="badge">Data Steward Dashboard</span>
        </div>
        <nav className="nav">
          {pages.map(p => (
            <button
              key={p}
              className={`nav-btn ${page === p ? 'active' : ''}`}
              onClick={() => setPage(p)}
            >
              {p === 'overview' ? '📊 Overview' :
               p === 'mock'     ? '🖥️ Mock Controls' :
               p === 'audit'    ? '📋 Audit Trail' :
               p === 'conflicts'? '⚔️ Conflicts' :
               p === 'dlq'      ? '📮 DLQ' :
                                  '🔐 BSA Verify'}
            </button>
          ))}
          <Link to="/portal" className="nav-btn nav-btn-portals">
            🏛️ Dept. Portals
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
          <span className={health?.status === 'healthy' ? 'badge-success' : 'badge-warning'}>
            {health?.status ?? 'unknown'}
          </span>
        </div>
        <table>
          <thead>
            <tr><th>Service</th><th>Status</th></tr>
          </thead>
          <tbody>
            {health?.checks && Object.entries(health.checks).map(([svc, status]) => (
              <tr key={svc}>
                <td style={{ textTransform: 'capitalize' }}>{svc}</td>
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

// ─── Mock Systems ─────────────────────────────────────────────────────────────

const SYSTEM_LABELS = {
  sws:       { label: 'SWS',              color: 'blue',   emoji: '🏛️' },
  shop:      { label: 'Shop Est.',         color: 'green',  emoji: '🏪' },
  factories: { label: 'Factories Dept.',   color: 'purple', emoji: '🏭' },
}

// Fields each system exposes for editing in the UI
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
      // Pre-populate edits with current values
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
      showToast(`✅ ${SYSTEM_LABELS[system].label} updated — SyncKar will propagate shortly`)
      await fetchRecord(system, selectedUbid)
    } catch (err) {
      showToast(`❌ Failed to update ${SYSTEM_LABELS[system].label}: ${err.message}`, 'error')
    } finally {
      setSaving(s => ({ ...s, [system]: false }))
    }
  }

  // ── Bug 4 fix: check response status, show error toast on 404 ──────────────
  const handleConflict = async () => {
    const swsBody = { registered_address: `${Date.now()} SWS Street, Bangalore 560001` }
    const factBody = { factory_address: `${Date.now()} Factory Lane, Bangalore 560002` }
    showToast('⚡ Triggering simultaneous conflict update…', 'info')

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
      showToast(`❌ Conflict trigger failed (${code}) — databases may be empty. Click 'Seed Data' first.`, 'error')
      return
    }

    showToast('⚔️ Conflict submitted — watch the Conflicts tab for SWS_WINS resolution')
    refreshAll(selectedUbid)
  }

  // ── Bug 5 fix: seed, reset, and scenario handlers ─────────────────────────
  const handleSeed = async () => {
    setSeeding(true)
    try {
      const res = await fetch(`${API_BASE}/api/mock/seed`, { method: 'POST' })
      if (!res.ok) throw new Error(`${res.status}`)
      const data = await res.json()
      showToast(`✅ Data seeded — SWS: ${data.seeded?.sws}, Shop: ${data.seeded?.shop}, Factories: ${data.seeded?.factories}`)
      refreshAll(selectedUbid)
    } catch (err) {
      showToast(`❌ Seed failed: ${err.message}`, 'error')
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
      showToast(`✅ Reset & reseeded — SWS: ${data.seeded?.sws}, Shop: ${data.seeded?.shop}, Factories: ${data.seeded?.factories}`)
      refreshAll(selectedUbid)
    } catch (err) {
      showToast(`❌ Reset failed: ${err.message}`, 'error')
    } finally {
      setSeeding(false)
    }
  }

  const handleScenarioA = async () => {
    // Scenario A: SWS → Dept — update address in SWS, SyncKar propagates to Shop + Factories
    const body = { registered_address: `${Date.now()} Scenario-A Street, Bengaluru 560001` }
    showToast('📤 Scenario A: updating SWS address…', 'info')
    try {
      const res = await fetch(`${API_BASE}/api/mock/sws/record/${selectedUbid}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`${res.status} — seed data first`)
      showToast('📤 Scenario A triggered — SWS address updated, SyncKar propagating to departments…')
      fetchRecord('sws', selectedUbid)
    } catch (err) {
      showToast(`❌ Scenario A failed: ${err.message}`, 'error')
    }
  }

  const handleScenarioB = async () => {
    // Scenario B: Dept → SWS — update address in Shop, SyncKar propagates back to SWS
    const body = { Buss_Addr_Line1: `${Date.now()} Scenario-B Road, Bengaluru 560002` }
    showToast('📥 Scenario B: updating Shop address…', 'info')
    try {
      const res = await fetch(`${API_BASE}/api/mock/shop/record/${selectedUbid}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`${res.status} — seed data first`)
      showToast('📥 Scenario B triggered — Shop address updated, SyncKar propagating to SWS…')
      fetchRecord('shop', selectedUbid)
    } catch (err) {
      showToast(`❌ Scenario B failed: ${err.message}`, 'error')
    }
  }

  const handleScenarioC = () => handleConflict()

  return (
    <div>
      {/* Toast */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>{toast.msg}</div>
      )}

      {/* Controls */}
      <div className="mock-controls">
        <div className="mock-controls-left">
          <label className="mock-label">Business (UBID)</label>
          {/* Bug 3 fix: all 20 UBIDs with business names */}
          <select
            className="mock-select"
            value={selectedUbid}
            onChange={e => setSelectedUbid(e.target.value)}
          >
            {UBID_LIST.map(u => (
              <option key={u.ubid} value={u.ubid}>{u.ubid} — {u.name}</option>
            ))}
          </select>
        </div>
        <div className="mock-controls-right">
          {/* Bug 5 fix: seed + reset buttons */}
          <button className="btn btn-seed" onClick={handleSeed} disabled={seeding}>
            {seeding ? 'Seeding…' : '🌱 Seed Data'}
          </button>
          <button className="btn btn-reset" onClick={handleReset} disabled={seeding}>
            {seeding ? 'Resetting…' : '🔄 Reset & Reseed'}
          </button>
          {/* Bug 5 fix: scenario buttons */}
          <button className="btn btn-scenario-a" onClick={handleScenarioA}>
            📤 Scenario A: SWS→Dept
          </button>
          <button className="btn btn-scenario-b" onClick={handleScenarioB}>
            📥 Scenario B: Dept→SWS
          </button>
          <button className="btn btn-conflict" onClick={handleScenarioC}>
            ⚔️ Scenario C: Conflict
          </button>
        </div>
      </div>
      <div className="mock-hint-row">
        <span className="mock-hint">Scenario A: SWS address → propagates to Shop &amp; Factories</span>
        <span className="mock-hint">Scenario B: Shop address → propagates back to SWS</span>
        <span className="mock-hint">Scenario C: simultaneous SWS + Factories update → SWS_WINS conflict</span>
      </div>

      {/* Three system panels */}
      <div className="mock-grid">
        {['sws', 'shop', 'factories'].map(system => {
          const { label, color, emoji } = SYSTEM_LABELS[system]
          const record = records[system]
          const fields = EDITABLE_FIELDS[system] || []
          const isLoading = loading[system]
          const isSaving = saving[system]
          const edit = edits[system] || {}

          return (
            <div key={system} className={`mock-panel mock-panel-${color}`}>
              <div className="mock-panel-header">
                <span className="mock-panel-title">{emoji} {label}</span>
                <span className="badge-info" style={{ fontSize: 10 }}>
                  {selectedUbid}
                </span>
              </div>

              {isLoading ? (
                <div className="mock-loading">Loading…</div>
              ) : !record ? (
                <div className="mock-empty">Record not found in {label}</div>
              ) : (
                <>
                  <div className="mock-readonly">
                    <div className="mock-field-row">
                      <span className="mock-field-label">Business Name</span>
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
                            {f.options.map(o => <option key={o} value={o}>{o}</option>)}
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
                    <span className="mock-modified">
                      Last modified: {record.last_modified?.slice(0, 19) ?? '—'}
                    </span>
                    <button
                      className={`btn btn-primary btn-sm ${isSaving ? 'btn-saving' : ''}`}
                      onClick={() => handleSave(system)}
                      disabled={isSaving}
                    >
                      {isSaving ? 'Saving…' : `Update ${label}`}
                    </button>
                  </div>
                </>
              )}
            </div>
          )
        })}
      </div>

      <div className="mock-tip">
        💡 After updating a field, switch to <strong>Overview</strong> or <strong>Audit Trail</strong> to watch SyncKar propagate the change in real time (auto-refreshes every 3–4s).
      </div>
    </div>
  )
}

// ─── Audit ────────────────────────────────────────────────────────────────────

function AuditPage({ audit, searchUbid, onSearch, onFetch }) {
  return (
    <div className="table-container">
      <div className="table-header">
        <h2>Audit Trail ({audit.length} entries)</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="search-input"
            placeholder="Search by UBID (e.g. KA-TEST-0001)"
            value={searchUbid}
            onChange={e => onSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && onFetch()}
          />
          <button className="btn btn-primary" onClick={onFetch}>Search</button>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>UBID</th>
            <th>Field</th>
            <th>Source → Target</th>
            <th>New Value</th>
            <th>Conflict</th>
          </tr>
        </thead>
        <tbody>
          {audit.map((row, i) => (
            <tr key={i}>
              <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {row.created_at?.slice(0, 19)}
              </td>
              <td><span className="badge-info">{row.ubid}</span></td>
              <td>{row.field_modified}</td>
              <td>{row.source_system} → {row.target_system}</td>
              <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {row.new_value?.slice(0, 40)}
              </td>
              <td>
                {row.conflict_detected ? (
                  <span className="badge-warning">{row.resolution_policy || 'YES'}</span>
                ) : (
                  <span className="badge-success">No</span>
                )}
              </td>
            </tr>
          ))}
          {audit.length === 0 && (
            <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>
              No audit entries. Use Mock Systems tab to trigger changes.
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
        <h2>⚔️ Conflict Log ({conflicts.length} records)</h2>
        <button className="btn btn-primary btn-sm" onClick={onRefresh}>Refresh</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>UBID</th>
            <th>Field</th>
            <th>Policy</th>
            <th>Winner ✅</th>
            <th>Loser (preserved) ❌</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {conflicts.map((c, i) => (
            <tr key={i}>
              <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.created_at?.slice(0, 19)}</td>
              <td><span className="badge-info">{c.ubid}</span></td>
              <td>{c.field}</td>
              <td><span className="badge-warning">{c.policy_applied}</span></td>
              <td style={{ color: 'var(--accent-green)' }}>{c.winning_value?.slice(0, 30)}</td>
              <td style={{ color: 'var(--accent-red)' }}>{c.losing_value?.slice(0, 30)}</td>
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
            <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>
              No conflicts. Use "Trigger Simultaneous Conflict" in Mock Systems tab.
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
        <h2>📮 Dead Letter Queue ({dlq.length} pending)</h2>
      </div>
      <table>
        <thead>
          <tr>
            <th>Time</th><th>UBID</th><th>Source</th>
            <th>Error Reason</th><th>Status</th><th>Action</th>
          </tr>
        </thead>
        <tbody>
          {dlq.map((item, i) => (
            <tr key={i}>
              <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.created_at?.slice(0, 19)}</td>
              <td><span className="badge-info">{item.ubid}</span></td>
              <td>{item.source_system}</td>
              <td style={{ maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.error_reason}</td>
              <td><span className="badge-error">{item.status}</span></td>
              <td><button className="btn btn-primary btn-sm">Resolve</button></td>
            </tr>
          ))}
          {dlq.length === 0 && (
            <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 32 }}>
              DLQ is empty. All events processed successfully. ✅
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

// ─── Verify ───────────────────────────────────────────────────────────────────

function VerifyPage({ audit, verifyResult, onVerify, onFetchAudit }) {
  useEffect(() => { onFetchAudit() }, [])

  return (
    <div>
      <div className="table-container">
        <div className="table-header">
          <h2>🔐 BSA 2023 Signature Verification</h2>
        </div>
        <table>
          <thead>
            <tr>
              <th>Audit ID</th><th>UBID</th><th>Field</th>
              <th>Source → Target</th><th>Action</th>
            </tr>
          </thead>
          <tbody>
            {audit.slice(0, 10).map((row, i) => (
              <tr key={i}>
                <td style={{ fontSize: 11, fontFamily: 'monospace' }}>{row.audit_id?.slice(0, 8)}…</td>
                <td><span className="badge-info">{row.ubid}</span></td>
                <td>{row.field_modified}</td>
                <td>{row.source_system} → {row.target_system}</td>
                <td>
                  <button className="btn btn-primary btn-sm" onClick={() => onVerify(row.audit_id)}>
                    Verify Signature
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {verifyResult && (
        <div className="verify-card">
          <h3 style={{ marginBottom: 12 }}>Verification Result</h3>
          <div className={`verify-result ${verifyResult.signature_valid ? 'valid' : 'invalid'}`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
              <span style={{ fontSize: 32 }}>
                {verifyResult.signature_valid ? '✅' : '❌'}
              </span>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>
                  {verifyResult.signature_valid ? 'Signature Valid' : 'Signature Invalid — TAMPERED'}
                </div>
                <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                  BSA 2023 Compliance: {verifyResult.bsa_2023_compliant ? 'PASSED' : 'FAILED'}
                </div>
              </div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
              <div>Audit ID: {verifyResult.audit_id}</div>
              <div>SHA-256: {verifyResult.payload_sha256?.slice(0, 32)}…</div>
              <div>UBID: {verifyResult.verification_details?.ubid}</div>
              <div>Field: {verifyResult.verification_details?.field}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App

import { useState, useEffect, useCallback } from 'react'
import './index.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

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

  useEffect(() => {
    fetchStats()
    fetchHealth()
    const interval = setInterval(fetchStats, 5000)
    return () => clearInterval(interval)
  }, [fetchStats, fetchHealth])

  useEffect(() => {
    if (page === 'audit') fetchAudit(searchUbid)
    if (page === 'conflicts') fetchConflicts()
    if (page === 'dlq') fetchDlq()
  }, [page, fetchAudit, fetchConflicts, fetchDlq, searchUbid])

  return (
    <div className="app">
      <header className="header">
        <div className="header-logo">
          <h1>⚡ SyncKar</h1>
          <span className="badge">Data Steward Dashboard</span>
        </div>
        <nav className="nav">
          {['overview', 'audit', 'conflicts', 'dlq', 'verify'].map(p => (
            <button
              key={p}
              className={`nav-btn ${page === p ? 'active' : ''}`}
              onClick={() => setPage(p)}
            >
              {p === 'overview' ? '📊 Overview' :
               p === 'audit' ? '📋 Audit Trail' :
               p === 'conflicts' ? '⚔️ Conflicts' :
               p === 'dlq' ? '📮 DLQ' :
               '🔐 BSA Verify'}
            </button>
          ))}
        </nav>
      </header>

      <main className="main">
        {page === 'overview' && <OverviewPage stats={stats} health={health} />}
        {page === 'audit' && (
          <AuditPage
            audit={audit}
            searchUbid={searchUbid}
            onSearch={setSearchUbid}
            onFetch={() => fetchAudit(searchUbid)}
          />
        )}
        {page === 'conflicts' && <ConflictsPage conflicts={conflicts} />}
        {page === 'dlq' && <DLQPage dlq={dlq} />}
        {page === 'verify' && (
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
            <tr>
              <th>Service</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {health?.checks && Object.entries(health.checks).map(([svc, status]) => (
              <tr key={svc}>
                <td style={{textTransform: 'capitalize'}}>{svc}</td>
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
              <td style={{fontSize: 11, color: 'var(--text-muted)'}}>
                {row.created_at?.slice(0, 19)}
              </td>
              <td><span className="badge-info">{row.ubid}</span></td>
              <td>{row.field_modified}</td>
              <td>{row.source_system} → {row.target_system}</td>
              <td style={{maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis'}}>
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
            <tr><td colSpan={6} style={{textAlign: 'center', color: 'var(--text-muted)', padding: 32}}>
              No audit entries found. Run a demo scenario to generate data.
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function ConflictsPage({ conflicts }) {
  return (
    <div className="table-container">
      <div className="table-header">
        <h2>⚔️ Conflict Log ({conflicts.length} records)</h2>
      </div>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>UBID</th>
            <th>Field</th>
            <th>Policy</th>
            <th>Winner</th>
            <th>Loser (preserved)</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {conflicts.map((c, i) => (
            <tr key={i}>
              <td style={{fontSize: 11, color: 'var(--text-muted)'}}>{c.created_at?.slice(0, 19)}</td>
              <td><span className="badge-info">{c.ubid}</span></td>
              <td>{c.field}</td>
              <td><span className="badge-warning">{c.policy_applied}</span></td>
              <td style={{color: 'var(--accent-green)'}}>{c.winning_value?.slice(0, 30)}</td>
              <td style={{color: 'var(--accent-red)'}}>{c.losing_value?.slice(0, 30)}</td>
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
            <tr><td colSpan={7} style={{textAlign: 'center', color: 'var(--text-muted)', padding: 32}}>
              No conflicts detected. Run Scenario C to generate conflicts.
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function DLQPage({ dlq }) {
  return (
    <div className="table-container">
      <div className="table-header">
        <h2>📮 Dead Letter Queue ({dlq.length} pending)</h2>
      </div>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>UBID</th>
            <th>Source</th>
            <th>Error Reason</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {dlq.map((item, i) => (
            <tr key={i}>
              <td style={{fontSize: 11, color: 'var(--text-muted)'}}>{item.created_at?.slice(0, 19)}</td>
              <td><span className="badge-info">{item.ubid}</span></td>
              <td>{item.source_system}</td>
              <td style={{maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis'}}>{item.error_reason}</td>
              <td><span className="badge-error">{item.status}</span></td>
              <td><button className="btn btn-primary btn-sm">Resolve</button></td>
            </tr>
          ))}
          {dlq.length === 0 && (
            <tr><td colSpan={6} style={{textAlign: 'center', color: 'var(--text-muted)', padding: 32}}>
              DLQ is empty. All events processed successfully. ✅
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

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
              <th>Audit ID</th>
              <th>UBID</th>
              <th>Field</th>
              <th>Source → Target</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {audit.slice(0, 10).map((row, i) => (
              <tr key={i}>
                <td style={{fontSize: 11, fontFamily: 'monospace'}}>{row.audit_id?.slice(0, 8)}...</td>
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
              <div>SHA-256: {verifyResult.payload_sha256?.slice(0, 32)}...</div>
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

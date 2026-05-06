/**
 * Mock Karnataka Single Window System (SWS) Portal
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import './portal.css'

const API_BASE = import.meta.env.VITE_API_URL || ''
const UBIDS = Array.from({ length: 20 }, (_, i) => `KA-TEST-${String(i + 1).padStart(4, '0')}`)

export default function PortalSWS() {
  const navigate = useNavigate()
  const loggedInUser = sessionStorage.getItem('mock_logged_in') || 'Demo Officer'
  const [selectedUbid, setSelectedUbid] = useState('KA-TEST-0001')
  const [record, setRecord] = useState(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({})
  const [toast, setToast] = useState(null)
  const [activity, setActivity] = useState([])
  const [inboundBanner, setInboundBanner] = useState(null)
  const lastModifiedRef = useRef(null)
  const [syncNotifications, setSyncNotifications] = useState([])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const fetchRecord = useCallback(async (ubid) => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/mock/sws/record/${ubid}`)
      if (!res.ok) throw new Error('Not found')
      const data = await res.json()
      setRecord(data)
      lastModifiedRef.current = data.last_modified
      setForm({
        registered_address: data.registered_address || '',
        authorized_signatory: data.authorized_signatory || '',
        primary_contact: data.primary_contact || '',
        employee_headcount: data.employee_headcount || 0,
        operational_status: data.operational_status || 'active',
        license_status: data.license_status || 'valid',
      })
    } catch {
      setRecord(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // Silent background refresh — picks up inbound SyncKar writes
  const silentRefresh = useCallback(async (ubid) => {
    try {
      const res = await fetch(`${API_BASE}/api/mock/sws/record/${ubid}`)
      if (!res.ok) return
      const data = await res.json()
      if (lastModifiedRef.current && data.last_modified !== lastModifiedRef.current) {
        setRecord(data)
        setInboundBanner('⟳ Record updated by SyncKar from another system')
        setTimeout(() => setInboundBanner(null), 5000)
      }
      lastModifiedRef.current = data.last_modified
    } catch { /* silent */ }
  }, [])

  useEffect(() => { fetchRecord(selectedUbid) }, [selectedUbid, fetchRecord])

  // Poll every 5s to catch inbound SyncKar propagations
  useEffect(() => {
    const id = setInterval(() => silentRefresh(selectedUbid), 5000)
    return () => clearInterval(id)
  }, [selectedUbid, silentRefresh])

  // Fetch SyncKar notifications for this UBID
  useEffect(() => {
    const fetchNotif = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/audit?ubid=${selectedUbid}&limit=5`)
        const data = await res.json()
        setSyncNotifications(data.audit_entries || [])
      } catch { /* silent */ }
    }
    fetchNotif()
    const id = setInterval(fetchNotif, 5000)
    return () => clearInterval(id)
  }, [selectedUbid])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = { ...form }
      // Auto-increment employee_headcount when nothing syncable has changed
      if (
        payload.registered_address === record?.registered_address &&
        payload.authorized_signatory === record?.authorized_signatory &&
        payload.primary_contact === record?.primary_contact &&
        String(payload.employee_headcount) === String(record?.employee_headcount) &&
        payload.operational_status === record?.operational_status &&
        payload.license_status === record?.license_status
      ) {
        payload.employee_headcount = (Number(payload.employee_headcount) || 0) + 1
        setForm(f => ({ ...f, employee_headcount: payload.employee_headcount }))
      }

      const res = await fetch(`${API_BASE}/api/mock/sws/record/${selectedUbid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error('Update failed')
      const data = await res.json()
      const updated = data.updated_fields || []

      if (updated.length === 0) {
        showToast('No fields were modified. SyncKar event not triggered.', 'warning')
      } else {
        showToast('Record updated. SyncKar is propagating changes.', 'success')
      }

      setActivity(a => [{
        time: new Date().toLocaleTimeString(),
        ubid: selectedUbid,
        fields: updated.length > 0 ? updated.join(', ') : 'No changes',
      }, ...a.slice(0, 9)])
      await fetchRecord(selectedUbid)
    } catch (err) {
      showToast(`Update failed: ${err.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="portal-root portal-sws">
      <header className="portal-header">
        <div className="portal-header-inner">
          <div className="portal-emblem">
            <div className="portal-emblem-circle">
              <svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect>
              </svg>
            </div>
            <div>
              <div className="portal-gov-name">Government of Karnataka</div>
              <div className="portal-dept-name">Single Window System</div>
            </div>
          </div>
          <div className="portal-header-right">
            <span className="portal-user">{loggedInUser}</span>
            <button 
              onClick={() => { sessionStorage.removeItem('mock_logged_in'); navigate('/portal/login'); }}
              style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.8)', fontSize: '0.75rem', cursor: 'pointer', textDecoration: 'underline' }}
            >
              Sign Out
            </button>
            <div className="portal-nav-links">
              <Link to="/portal/shop" className="portal-nav-link">Shop Portal</Link>
              <Link to="/portal/factories" className="portal-nav-link">Factories Portal</Link>
              <Link to="/" className="portal-nav-link portal-nav-link-dashboard">SyncKar Dashboard</Link>
            </div>
          </div>
        </div>
        <div className="portal-breadcrumb">
          <div className="portal-breadcrumb-inner">
            Home &rsaquo; Business Services &rsaquo; Manage Record
          </div>
        </div>
      </header>

      {toast && <div className={`portal-toast portal-toast-${toast.type}`}>{toast.msg}</div>}
      {inboundBanner && (
        <div className="portal-toast portal-toast-info" style={{ background: '#dbeafe', color: '#1d4ed8', borderColor: '#93c5fd' }}>
          {inboundBanner}
        </div>
      )}

      <main className="portal-main">
        <div className="portal-page-title">
          <h1>Manage Business Record</h1>
          <p>Update authoritative business details. Changes made here are automatically synced to other departments.</p>
        </div>

        <div className="portal-layout">
          <div className="portal-form-section">
            <div className="portal-card">
              <div className="portal-card-header sws-header">
                <span>Record Editor</span>
                <select
                  name="selectedUbid"
                  autoComplete="off"
                  className="portal-ubid-select"
                  value={selectedUbid}
                  onChange={e => setSelectedUbid(e.target.value)}
                >
                  {UBIDS.map(u => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>

              {loading ? (
                <div className="portal-loading">Loading record details…</div>
              ) : !record ? (
                <div className="portal-empty">Record not found for {selectedUbid}. Please seed the database.</div>
              ) : (
                <form onSubmit={handleSubmit} className="portal-form">
                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>Target ID (UBID)</label>
                      <input type="text" value={selectedUbid} disabled className="portal-input portal-input-disabled" />
                    </div>
                    <div className="portal-field">
                      <label>Business Name</label>
                      <input type="text" value={record.business_name || ''} disabled className="portal-input portal-input-disabled" />
                    </div>
                  </div>

                  <div className="portal-field">
                    <label>Registered Address <span className="portal-required">*</span></label>
                    <input
                      type="text"
                      name="registered_address"
                      autoComplete="street-address"
                      className="portal-input"
                      value={form.registered_address}
                      onChange={e => setForm(f => ({ ...f, registered_address: e.target.value }))}
                    />
                    <span className="portal-hint">Authoritative field. Will overwrite department records.</span>
                  </div>

                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>Authorized Signatory</label>
                      <input
                        type="text"
                        name="authorized_signatory"
                        autoComplete="name"
                        className="portal-input"
                        value={form.authorized_signatory}
                        onChange={e => setForm(f => ({ ...f, authorized_signatory: e.target.value }))}
                      />
                    </div>
                    <div className="portal-field">
                      <label>Primary Contact</label>
                      <input
                        type="text"
                        name="primary_contact"
                        autoComplete="tel"
                        className="portal-input"
                        value={form.primary_contact}
                        onChange={e => setForm(f => ({ ...f, primary_contact: e.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="portal-section-label">Compliance & Status</div>

                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>Employee Headcount</label>
                      <input
                        type="number"
                        name="employee_headcount"
                        autoComplete="off"
                        className="portal-input"
                        value={form.employee_headcount}
                        onChange={e => setForm(f => ({ ...f, employee_headcount: Number(e.target.value) }))}
                      />
                    </div>
                    <div className="portal-field">
                      <label>Operational Status</label>
                      <select
                        name="operational_status"
                        className="portal-input"
                        value={form.operational_status}
                        onChange={e => setForm(f => ({ ...f, operational_status: e.target.value }))}
                      >
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                        <option value="suspended">Suspended</option>
                      </select>
                    </div>
                    <div className="portal-field">
                      <label>License Status</label>
                      <select
                        name="license_status"
                        className="portal-input"
                        value={form.license_status}
                        onChange={e => setForm(f => ({ ...f, license_status: e.target.value }))}
                      >
                        <option value="valid">Valid</option>
                        <option value="expired">Expired</option>
                        <option value="revoked">Revoked</option>
                      </select>
                    </div>
                  </div>

                  <div className="portal-form-footer">
                    <button type="submit" className="portal-btn portal-btn-primary" disabled={saving}>
                      {saving ? 'Updating...' : 'Save Changes'}
                    </button>
                    <div className="portal-sync-note">
                      <strong>Note:</strong> Saving will trigger a SyncKar event. Other departments will be updated automatically.
                    </div>
                  </div>
                </form>
              )}
            </div>
          </div>

          <div className="portal-sidebar">
            <div className="portal-card">
              <div className="portal-card-header sws-header">Current Data</div>
              {record && (
                <div className="portal-record-view">
                  {[
                    ['UBID', selectedUbid],
                    ['Business', record.business_name],
                    ['Address', record.registered_address],
                    ['Signatory', record.authorized_signatory],
                    ['Contact', record.primary_contact],
                    ['Headcount', record.employee_headcount],
                    ['Status', record.operational_status],
                    ['Last Updated', record.last_modified?.slice(0, 19).replace('T', ' ')],
                  ].map(([k, v]) => (
                    <div key={k} className="portal-record-row">
                      <span className="portal-record-key">{k}</span>
                      <span className="portal-record-val">{v || '—'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="portal-card">
              <div className="portal-card-header sws-header">Recent Activity</div>
              {activity.length === 0 ? (
                <div className="portal-empty-sm">No recent updates.</div>
              ) : (
                <div className="portal-activity">
                  {activity.map((a, i) => (
                    <div key={i} className="portal-activity-row">
                      <span className="portal-activity-time">{a.time}</span>
                      <span className="portal-activity-fields">Updated: {a.fields}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="portal-card">
              <div className="portal-card-header sws-header">
                <span>SyncKar Notifications</span>
                {syncNotifications.length > 0 && <span className="portal-notification-badge">{syncNotifications.length}</span>}
              </div>
              {syncNotifications.length === 0 ? (
                <div className="portal-empty-sm">No cross-system events for this record yet.</div>
              ) : (
                <>
                  <div className="portal-notification-panel">
                    {syncNotifications.map((n, i) => (
                      <div key={i} className="portal-notification-row">
                        <div className={`portal-notification-dot${n.conflict_detected ? ' conflict' : ''}`} />
                        <div className="portal-notification-content">
                          <div className="portal-notification-text">
                            <strong>{n.field_modified}</strong> synced from <em>{n.source_system}</em> → <em>{n.target_system}</em>
                            {n.conflict_detected && <span style={{ color: '#d97706', fontWeight: 600 }}> (Conflict Resolved)</span>}
                          </div>
                          <div className="portal-notification-time">{n.created_at?.slice(0, 19).replace('T', ' ')}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <Link to="/" className="portal-dashboard-link">View Full Dashboard →</Link>
                </>
              )}
            </div>
          </div>
        </div>
      </main>

      <footer className="portal-footer">
        <div>&copy; 2026 Government of Karnataka</div>
        <div>Powered by SyncKar</div>
      </footer>
    </div>
  )
}

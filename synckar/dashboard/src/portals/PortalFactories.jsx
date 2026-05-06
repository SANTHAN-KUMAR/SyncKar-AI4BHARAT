/**
 * Mock Factories Department Portal
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import './portal.css'

const API_BASE = import.meta.env.VITE_API_URL || ''
const UBIDS = Array.from({ length: 20 }, (_, i) => `KA-TEST-${String(i + 1).padStart(4, '0')}`)

export default function PortalFactories() {
  const [selectedUbid, setSelectedUbid] = useState('KA-TEST-0001')
  const [record, setRecord] = useState(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState({})
  const [toast, setToast] = useState(null)
  const [activity, setActivity] = useState([])
  const [inboundBanner, setInboundBanner] = useState(null)
  const lastModifiedRef = useRef(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const fetchRecord = useCallback(async (ubid) => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/mock/factories/record/${ubid}`)
      if (!res.ok) throw new Error('Not found')
      const data = await res.json()
      setRecord(data)
      lastModifiedRef.current = data.last_modified
      setForm({
        factory_address: data.factory_address || '',
        signatory_name: data.signatory_name || '',
        contact_number: data.contact_number || '',
        worker_count: data.worker_count || 0,
        factory_status: data.factory_status || 'active',
        hazard_category: data.hazard_category || 'low',
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
      const res = await fetch(`${API_BASE}/api/mock/factories/record/${ubid}`)
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

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = { ...form }
      // Auto-increment worker_count when nothing syncable has changed
      if (
        payload.factory_address === record?.factory_address &&
        payload.signatory_name  === record?.signatory_name &&
        payload.contact_number  === record?.contact_number &&
        String(payload.worker_count) === String(record?.worker_count) &&
        payload.factory_status  === record?.factory_status
      ) {
        payload.worker_count = (Number(payload.worker_count) || 0) + 1
        setForm(f => ({ ...f, worker_count: payload.worker_count }))
      }

      const res = await fetch(`${API_BASE}/api/mock/factories/record/${selectedUbid}`, {
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
    <div className="portal-root portal-factories">
      <header className="portal-header">
        <div className="portal-header-inner">
          <div className="portal-emblem">
            <div className="portal-emblem-circle factories-emblem">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 20h20M4 20V4l8 6 8-6v16"></path>
              </svg>
            </div>
            <div>
              <div className="portal-gov-name">Dept. of Factories & Boilers</div>
              <div className="portal-dept-name">Factories Portal</div>
            </div>
          </div>
          <div className="portal-header-right">
            <span className="portal-user">Director Anil P.</span>
            <div className="portal-nav-links">
              <Link to="/portal/sws" className="portal-nav-link">SWS Portal</Link>
              <Link to="/portal/shop" className="portal-nav-link">Shop Portal</Link>
              <Link to="/" className="portal-nav-link portal-nav-link-dashboard">SyncKar Dashboard</Link>
            </div>
          </div>
        </div>
        <div className="portal-breadcrumb">
          <div className="portal-breadcrumb-inner">
            Home &rsaquo; Factories &rsaquo; Manage Record
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
          <h1>Manage Factory Compliance Record</h1>
          <p>Update factory details. Demographic data is managed by SWS, while compliance data is managed locally.</p>
        </div>

        <div className="portal-layout">
          <div className="portal-form-section">
            <div className="portal-card">
              <div className="portal-card-header factories-header-card">
                <span>Record Editor</span>
                <select
                  className="portal-ubid-select"
                  value={selectedUbid}
                  onChange={e => setSelectedUbid(e.target.value)}
                >
                  {UBIDS.map(u => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>

              {loading ? (
                <div className="portal-loading">Loading record details...</div>
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
                    <label>Factory Address</label>
                    <input
                      type="text"
                      className="portal-input"
                      value={form.factory_address}
                      onChange={e => setForm(f => ({ ...f, factory_address: e.target.value }))}
                    />
                    <span className="portal-hint">Warning: SWS is the authoritative source. Changes here may trigger a conflict.</span>
                  </div>

                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>Signatory Name</label>
                      <input
                        type="text"
                        className="portal-input"
                        value={form.signatory_name}
                        onChange={e => setForm(f => ({ ...f, signatory_name: e.target.value }))}
                      />
                    </div>
                    <div className="portal-field">
                      <label>Contact Number</label>
                      <input
                        type="text"
                        className="portal-input"
                        value={form.contact_number}
                        onChange={e => setForm(f => ({ ...f, contact_number: e.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="portal-section-label">Safety & Compliance (Local)</div>
                  
                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>Worker Count</label>
                      <input
                        type="number"
                        className="portal-input"
                        value={form.worker_count}
                        onChange={e => setForm(f => ({ ...f, worker_count: Number(e.target.value) }))}
                      />
                    </div>
                    <div className="portal-field">
                      <label>Factory Status</label>
                      <select
                        className="portal-input"
                        value={form.factory_status}
                        onChange={e => setForm(f => ({ ...f, factory_status: e.target.value }))}
                      >
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                        <option value="suspended">Suspended</option>
                      </select>
                    </div>
                    <div className="portal-field">
                      <label>Hazard Category</label>
                      <select
                        className="portal-input"
                        value={form.hazard_category}
                        onChange={e => setForm(f => ({ ...f, hazard_category: e.target.value }))}
                      >
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="extreme">Extreme</option>
                      </select>
                      <span className="portal-hint">Local field. Not synced by SyncKar.</span>
                    </div>
                  </div>

                  <div className="portal-form-footer">
                    <button type="submit" className="portal-btn portal-btn-factories" disabled={saving}>
                      {saving ? 'Updating...' : 'Save Changes'}
                    </button>
                    <div className="portal-sync-note factories-sync-note">
                      <strong>Note:</strong> Shared fields will be propagated to SWS and other departments via SyncKar.
                    </div>
                  </div>
                </form>
              )}
            </div>
          </div>

          <div className="portal-sidebar">
            <div className="portal-card">
              <div className="portal-card-header factories-header-card">Current Data</div>
              {record && (
                <div className="portal-record-view">
                  {[
                    ['UBID', selectedUbid],
                    ['Business', record.business_name],
                    ['Address', record.factory_address],
                    ['Signatory', record.signatory_name],
                    ['Contact', record.contact_number],
                    ['Workers', record.worker_count],
                    ['Status', record.factory_status],
                    ['Hazard', record.hazard_category],
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
              <div className="portal-card-header factories-header-card">Recent Activity</div>
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
          </div>
        </div>
      </main>

      <footer className="portal-footer">
        <div>&copy; 2026 Government of Karnataka — Dept. of Factories & Boilers</div>
        <div>Powered by SyncKar</div>
      </footer>
    </div>
  )
}

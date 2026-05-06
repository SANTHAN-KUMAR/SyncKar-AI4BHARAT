/**
 * Mock Shop Establishment Portal
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import './portal.css'

const API_BASE = import.meta.env.VITE_API_URL || ''
const UBIDS = Array.from({ length: 20 }, (_, i) => `KA-TEST-${String(i + 1).padStart(4, '0')}`)

export default function PortalShop() {
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
      const res = await fetch(`${API_BASE}/api/mock/shop/record/${ubid}`)
      if (!res.ok) throw new Error('Not found')
      const data = await res.json()
      setRecord(data)
      lastModifiedRef.current = data.last_modified
      setForm({
        Buss_Addr_Line1: data.Buss_Addr_Line1 || '',
        Auth_Sign_Name: data.Auth_Sign_Name || '',
        Contact_Phone: data.Contact_Phone || '',
        Emp_Count: data.Emp_Count || 0,
        Op_Status: data.Op_Status || 'active',
        Compliance_Score: data.Compliance_Score || 100,
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
      const res = await fetch(`${API_BASE}/api/mock/shop/record/${ubid}`)
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
      // Auto-increment Emp_Count when nothing has changed, so a real event fires
      if (
        payload.Buss_Addr_Line1 === record?.Buss_Addr_Line1 &&
        payload.Auth_Sign_Name  === record?.Auth_Sign_Name &&
        payload.Contact_Phone   === record?.Contact_Phone &&
        String(payload.Emp_Count) === String(record?.Emp_Count) &&
        payload.Op_Status       === record?.Op_Status
      ) {
        payload.Emp_Count = (Number(payload.Emp_Count) || 0) + 1
        setForm(f => ({ ...f, Emp_Count: payload.Emp_Count }))
      }

      const res = await fetch(`${API_BASE}/api/mock/shop/record/${selectedUbid}`, {
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
    <div className="portal-root portal-shop">
      <header className="portal-header">
        <div className="portal-header-inner">
          <div className="portal-emblem">
            <div className="portal-emblem-circle shop-emblem">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              </svg>
            </div>
            <div>
              <div className="portal-gov-name">Department of Labour</div>
              <div className="portal-dept-name">Shop Establishment Portal</div>
            </div>
          </div>
          <div className="portal-header-right">
            <span className="portal-user">Inspector Vivek S.</span>
            <div className="portal-nav-links">
              <Link to="/portal/sws" className="portal-nav-link">SWS Portal</Link>
              <Link to="/portal/factories" className="portal-nav-link">Factories Portal</Link>
              <Link to="/" className="portal-nav-link portal-nav-link-dashboard">SyncKar Dashboard</Link>
            </div>
          </div>
        </div>
        <div className="portal-breadcrumb">
          <div className="portal-breadcrumb-inner">
            Home &rsaquo; Establishments &rsaquo; Manage Record
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
          <h1>Manage Establishment Record</h1>
          <p>Update shop details. Demographic data is managed by SWS, while compliance data is managed locally.</p>
        </div>

        <div className="portal-layout">
          <div className="portal-form-section">
            <div className="portal-card">
              <div className="portal-card-header shop-header">
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
                    <label>Business Address</label>
                    <input
                      type="text"
                      className="portal-input"
                      value={form.Buss_Addr_Line1}
                      onChange={e => setForm(f => ({ ...f, Buss_Addr_Line1: e.target.value }))}
                    />
                    <span className="portal-hint">Warning: SWS is the authoritative source. Changes here may trigger a conflict.</span>
                  </div>

                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>Authorized Signatory</label>
                      <input
                        type="text"
                        className="portal-input"
                        value={form.Auth_Sign_Name}
                        onChange={e => setForm(f => ({ ...f, Auth_Sign_Name: e.target.value }))}
                      />
                    </div>
                    <div className="portal-field">
                      <label>Contact Phone</label>
                      <input
                        type="text"
                        className="portal-input"
                        value={form.Contact_Phone}
                        onChange={e => setForm(f => ({ ...f, Contact_Phone: e.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="portal-section-label">Labour Compliance (Local)</div>
                  
                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>Employee Count</label>
                      <input
                        type="number"
                        className="portal-input"
                        value={form.Emp_Count}
                        onChange={e => setForm(f => ({ ...f, Emp_Count: Number(e.target.value) }))}
                      />
                    </div>
                    <div className="portal-field">
                      <label>Operational Status</label>
                      <select
                        className="portal-input"
                        value={form.Op_Status}
                        onChange={e => setForm(f => ({ ...f, Op_Status: e.target.value }))}
                      >
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                        <option value="suspended">Suspended</option>
                      </select>
                    </div>
                    <div className="portal-field">
                      <label>Compliance Score (0-100)</label>
                      <input
                        type="number"
                        className="portal-input"
                        value={form.Compliance_Score}
                        onChange={e => setForm(f => ({ ...f, Compliance_Score: Number(e.target.value) }))}
                        min={0} max={100}
                      />
                      <span className="portal-hint">Local field. Not synced by SyncKar.</span>
                    </div>
                  </div>

                  <div className="portal-form-footer">
                    <button type="submit" className="portal-btn portal-btn-shop" disabled={saving}>
                      {saving ? 'Updating...' : 'Save Changes'}
                    </button>
                    <div className="portal-sync-note shop-sync-note">
                      <strong>Note:</strong> Shared fields will be propagated to SWS and other departments via SyncKar.
                    </div>
                  </div>
                </form>
              )}
            </div>
          </div>

          <div className="portal-sidebar">
            <div className="portal-card">
              <div className="portal-card-header shop-header">Current Data</div>
              {record && (
                <div className="portal-record-view">
                  {[
                    ['UBID', selectedUbid],
                    ['Business', record.business_name],
                    ['Address', record.Buss_Addr_Line1],
                    ['Signatory', record.Auth_Sign_Name],
                    ['Contact', record.Contact_Phone],
                    ['Employees', record.Emp_Count],
                    ['Status', record.Op_Status],
                    ['Compliance', record.Compliance_Score != null ? `${record.Compliance_Score}/100` : 'N/A'],
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
              <div className="portal-card-header shop-header">Recent Activity</div>
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
        <div>&copy; 2026 Government of Karnataka — Department of Labour</div>
        <div>Powered by SyncKar</div>
      </footer>
    </div>
  )
}

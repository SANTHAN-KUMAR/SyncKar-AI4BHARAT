/**
 * Mock Shop Establishment Portal
 */
import { useState, useEffect, useCallback } from 'react'
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

  useEffect(() => { fetchRecord(selectedUbid) }, [selectedUbid, fetchRecord])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/mock/shop/record/${selectedUbid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error('Update failed')
      const data = await res.json()
      const updated = data.updated_fields || []
      showToast(`RECORD UPDATED. FIELDS: ${updated.join(', ') || 'NONE'}`, 'success')
      setActivity(a => [{
        time: new Date().toLocaleTimeString(),
        ubid: selectedUbid,
        fields: updated.join(', ') || '—',
      }, ...a.slice(0, 9)])
      await fetchRecord(selectedUbid)
    } catch (err) {
      showToast(`UPDATE FAILED: ${err.message}`, 'error')
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
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              </svg>
            </div>
            <div>
              <div className="portal-gov-name">Department of Labour</div>
              <div className="portal-dept-name">Shop Establishment Portal</div>
            </div>
          </div>
          <div className="portal-header-right">
            <span className="portal-user">INSPECTOR VIVEK S. | LABOUR DEPT</span>
            <div className="portal-nav-links">
              <Link to="/portal/sws" className="portal-nav-link">SWS</Link>
              <Link to="/portal/factories" className="portal-nav-link">FACTORIES</Link>
              <Link to="/" className="portal-nav-link portal-nav-link-dashboard">DASHBOARD</Link>
            </div>
          </div>
        </div>
        <div className="portal-breadcrumb">
          HOME &rsaquo; ESTABLISHMENTS &rsaquo; UPDATE RECORD
        </div>
      </header>

      {toast && <div className={`portal-toast portal-toast-${toast.type}`}>{toast.msg}</div>}

      <main className="portal-main">
        <div className="portal-page-title shop-title">
          <h1>Shop / Establishment Record</h1>
          <p>MUTATIONS ARE AUTOMATICALLY PROPAGATED VIA SYNCKAR EVENT BUS.</p>
        </div>

        <div className="portal-layout">
          <div className="portal-form-section">
            <div className="portal-card">
              <div className="portal-card-header shop-header">
                <span>ENTITY DETAILS &mdash; SHOP</span>
                <select
                  className="portal-ubid-select"
                  value={selectedUbid}
                  onChange={e => setSelectedUbid(e.target.value)}
                >
                  {UBIDS.map(u => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>

              {loading ? (
                <div className="portal-loading">
                  <div className="portal-spinner shop-spinner" />
                  FETCHING RECORD...
                </div>
              ) : !record ? (
                <div className="portal-empty">ENTITY {selectedUbid} NOT FOUND</div>
              ) : (
                <form onSubmit={handleSubmit} className="portal-form">
                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>TARGET ID (UBID)</label>
                      <input type="text" value={selectedUbid} disabled className="portal-input portal-input-disabled" />
                    </div>
                    <div className="portal-field">
                      <label>ENTITY NAME (READ-ONLY)</label>
                      <input type="text" value={record.business_name || ''} disabled className="portal-input portal-input-disabled" />
                      <span className="portal-hint">CONTROLLED BY SWS</span>
                    </div>
                  </div>

                  <div className="portal-field">
                    <label>BUSINESS ADDRESS <span className="portal-required">*</span></label>
                    <input
                      type="text"
                      className="portal-input"
                      value={form.Buss_Addr_Line1}
                      onChange={e => setForm(f => ({ ...f, Buss_Addr_Line1: e.target.value }))}
                    />
                    <span className="portal-hint">NOTE: SWS IS AUTHORITATIVE. OVERWRITES MAY BE REVERTED ON CONFLICT.</span>
                  </div>

                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>AUTHORIZED SIGNATORY</label>
                      <input
                        type="text"
                        className="portal-input"
                        value={form.Auth_Sign_Name}
                        onChange={e => setForm(f => ({ ...f, Auth_Sign_Name: e.target.value }))}
                      />
                    </div>
                    <div className="portal-field">
                      <label>CONTACT PHONE</label>
                      <input
                        type="text"
                        className="portal-input"
                        value={form.Contact_Phone}
                        onChange={e => setForm(f => ({ ...f, Contact_Phone: e.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="portal-section-label">LABOUR COMPLIANCE</div>
                  
                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>EMPLOYEE COUNT</label>
                      <input
                        type="number"
                        className="portal-input"
                        value={form.Emp_Count}
                        onChange={e => setForm(f => ({ ...f, Emp_Count: Number(e.target.value) }))}
                        min={0}
                      />
                    </div>
                    <div className="portal-field">
                      <label>OPERATIONAL STATUS</label>
                      <select
                        className="portal-input"
                        value={form.Op_Status}
                        onChange={e => setForm(f => ({ ...f, Op_Status: e.target.value }))}
                      >
                        <option value="active">ACTIVE</option>
                        <option value="inactive">INACTIVE</option>
                        <option value="suspended">SUSPENDED</option>
                      </select>
                    </div>
                    <div className="portal-field">
                      <label>COMPLIANCE SCORE (0-100)</label>
                      <input
                        type="number"
                        className="portal-input portal-input-compliance"
                        value={form.Compliance_Score}
                        onChange={e => setForm(f => ({ ...f, Compliance_Score: Number(e.target.value) }))}
                        min={0} max={100}
                      />
                      <span className="portal-hint">LOCAL FIELD ONLY. DO NOT SYNC.</span>
                    </div>
                  </div>

                  <div className="portal-form-footer">
                    <div className="portal-sync-note shop-sync-note">
                      SYNCKAR WILL DETECT THIS MUTATION AND PROPAGATE IT TO CONNECTED SYSTEMS.
                    </div>
                    <button type="submit" className="portal-btn portal-btn-shop" disabled={saving}>
                      {saving ? 'EXECUTING...' : 'COMMIT UPDATE'}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>

          <div className="portal-sidebar">
            <div className="portal-card">
              <div className="portal-card-header shop-header">CURRENT RECORD STATE</div>
              {record && (
                <div className="portal-record-view">
                  {[
                    ['UBID', selectedUbid],
                    ['Entity', record.business_name],
                    ['Address', record.Buss_Addr_Line1],
                    ['Signatory', record.Auth_Sign_Name],
                    ['Contact', record.Contact_Phone],
                    ['Employees', record.Emp_Count],
                    ['Status', record.Op_Status],
                    ['Compliance', `${record.Compliance_Score}/100`],
                    ['Modified', record.last_modified?.slice(0, 19)],
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
              <div className="portal-card-header shop-header">SESSION ACTIVITY</div>
              {activity.length === 0 ? (
                <div className="portal-empty-sm">NO MUTATIONS RECORDED</div>
              ) : (
                <div className="portal-activity">
                  {activity.map((a, i) => (
                    <div key={i} className="portal-activity-row">
                      <span className="portal-activity-time">{a.time}</span>
                      <span className="portal-activity-ubid">{a.ubid}</span>
                      <span className="portal-activity-fields">{a.fields}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      <footer className="portal-footer shop-footer">
        <div>GOVERNMENT OF KARNATAKA — SHOP TERMINAL</div>
        <div>POWERED BY SYNCKAR INTEROPERABILITY LAYER</div>
      </footer>
    </div>
  )
}

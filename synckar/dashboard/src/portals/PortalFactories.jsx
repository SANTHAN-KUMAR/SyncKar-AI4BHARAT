/**
 * Mock Factories Department Portal
 */
import { useState, useEffect, useCallback } from 'react'
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

  useEffect(() => { fetchRecord(selectedUbid) }, [selectedUbid, fetchRecord])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/mock/factories/record/${selectedUbid}`, {
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
    <div className="portal-root portal-factories">
      <header className="portal-header">
        <div className="portal-header-inner">
          <div className="portal-emblem">
            <div className="portal-emblem-circle factories-emblem">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M2 20h20M4 20V4l8 6 8-6v16"></path>
              </svg>
            </div>
            <div>
              <div className="portal-gov-name">Dept. of Factories & Boilers</div>
              <div className="portal-dept-name">Factories Portal</div>
            </div>
          </div>
          <div className="portal-header-right">
            <span className="portal-user">DIRECTOR ANIL P. | FACTORIES DEPT</span>
            <div className="portal-nav-links">
              <Link to="/portal/sws" className="portal-nav-link">SWS</Link>
              <Link to="/portal/shop" className="portal-nav-link">SHOP EST.</Link>
              <Link to="/" className="portal-nav-link portal-nav-link-dashboard">DASHBOARD</Link>
            </div>
          </div>
        </div>
        <div className="portal-breadcrumb">
          HOME &rsaquo; FACTORIES &rsaquo; UPDATE RECORD
        </div>
      </header>

      {toast && <div className={`portal-toast portal-toast-${toast.type}`}>{toast.msg}</div>}

      <main className="portal-main">
        <div className="portal-page-title factories-title">
          <h1>Factory Compliance Record</h1>
          <p>MUTATIONS ARE AUTOMATICALLY PROPAGATED VIA SYNCKAR EVENT BUS.</p>
        </div>

        <div className="portal-layout">
          <div className="portal-form-section">
            <div className="portal-card">
              <div className="portal-card-header factories-header-card">
                <span>ENTITY DETAILS &mdash; FACTORIES</span>
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
                  <div className="portal-spinner factories-spinner" />
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
                    <label>FACTORY ADDRESS <span className="portal-required">*</span></label>
                    <input
                      type="text"
                      className="portal-input"
                      value={form.factory_address}
                      onChange={e => setForm(f => ({ ...f, factory_address: e.target.value }))}
                    />
                    <span className="portal-hint">NOTE: SWS IS AUTHORITATIVE. OVERWRITES MAY BE REVERTED ON CONFLICT.</span>
                  </div>

                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>SIGNATORY NAME</label>
                      <input
                        type="text"
                        className="portal-input"
                        value={form.signatory_name}
                        onChange={e => setForm(f => ({ ...f, signatory_name: e.target.value }))}
                      />
                    </div>
                    <div className="portal-field">
                      <label>CONTACT NUMBER</label>
                      <input
                        type="text"
                        className="portal-input"
                        value={form.contact_number}
                        onChange={e => setForm(f => ({ ...f, contact_number: e.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="portal-section-label">SAFETY & COMPLIANCE</div>
                  
                  <div className="portal-form-row">
                    <div className="portal-field">
                      <label>WORKER COUNT</label>
                      <input
                        type="number"
                        className="portal-input"
                        value={form.worker_count}
                        onChange={e => setForm(f => ({ ...f, worker_count: Number(e.target.value) }))}
                        min={0}
                      />
                    </div>
                    <div className="portal-field">
                      <label>FACTORY STATUS</label>
                      <select
                        className="portal-input"
                        value={form.factory_status}
                        onChange={e => setForm(f => ({ ...f, factory_status: e.target.value }))}
                      >
                        <option value="active">ACTIVE</option>
                        <option value="inactive">INACTIVE</option>
                        <option value="suspended">SUSPENDED</option>
                      </select>
                    </div>
                    <div className="portal-field">
                      <label>HAZARD CATEGORY</label>
                      <select
                        className="portal-input portal-input-compliance"
                        value={form.hazard_category}
                        onChange={e => setForm(f => ({ ...f, hazard_category: e.target.value }))}
                      >
                        <option value="low">LOW</option>
                        <option value="medium">MEDIUM</option>
                        <option value="high">HIGH</option>
                        <option value="extreme">EXTREME</option>
                      </select>
                      <span className="portal-hint">LOCAL FIELD ONLY. DO NOT SYNC.</span>
                    </div>
                  </div>

                  <div className="portal-form-footer">
                    <div className="portal-sync-note factories-sync-note">
                      SYNCKAR WILL DETECT THIS MUTATION AND PROPAGATE IT TO CONNECTED SYSTEMS.
                    </div>
                    <button type="submit" className="portal-btn portal-btn-factories" disabled={saving}>
                      {saving ? 'EXECUTING...' : 'COMMIT UPDATE'}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>

          <div className="portal-sidebar">
            <div className="portal-card">
              <div className="portal-card-header factories-header-card">CURRENT RECORD STATE</div>
              {record && (
                <div className="portal-record-view">
                  {[
                    ['UBID', selectedUbid],
                    ['Entity', record.business_name],
                    ['Address', record.factory_address],
                    ['Signatory', record.signatory_name],
                    ['Contact', record.contact_number],
                    ['Workers', record.worker_count],
                    ['Status', record.factory_status],
                    ['Hazard', record.hazard_category],
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
              <div className="portal-card-header factories-header-card">SESSION ACTIVITY</div>
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

      <footer className="portal-footer factories-footer">
        <div>GOVERNMENT OF KARNATAKA — FACTORIES TERMINAL</div>
        <div>POWERED BY SYNCKAR INTEROPERABILITY LAYER</div>
      </footer>
    </div>
  )
}

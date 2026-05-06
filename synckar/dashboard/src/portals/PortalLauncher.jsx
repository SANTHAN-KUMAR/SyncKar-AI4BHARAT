/**
 * Portal Launcher — entry page showing all three department portals
 */
import { Link } from 'react-router-dom'
import './portal.css'

export default function PortalLauncher() {
  return (
    <div className="portal-launcher-root">
      <div className="portal-launcher">
        <div className="portal-launcher-header">
          <div className="portal-launcher-emblem">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
              <polyline points="2 17 12 22 22 17"></polyline>
              <polyline points="2 12 12 17 22 12"></polyline>
            </svg>
          </div>
          <h1>Gov. Karnataka Portals</h1>
          <p className="portal-launcher-sub">
            PROTOTYPE ENVIRONMENT · SYNCKAR INTEROPERABILITY LAYER
          </p>
        </div>

        <div className="portal-launcher-cards">
          <Link to="/portal/sws" className="portal-launcher-card portal-launcher-card-sws">
            <div className="portal-launcher-icon">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect>
              </svg>
            </div>
            <div className="portal-launcher-name">Single Window</div>
            <div className="portal-launcher-desc">Business Registration & Services. Primary authority for demographic data.</div>
            <div className="portal-launcher-tag">Primary Authority</div>
          </Link>

          <Link to="/portal/shop" className="portal-launcher-card portal-launcher-card-shop">
            <div className="portal-launcher-icon">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              </svg>
            </div>
            <div className="portal-launcher-name">Shop Est. Dept.</div>
            <div className="portal-launcher-desc">Department of Labour — Shop & Establishment Registrations.</div>
            <div className="portal-launcher-tag">Department Portal</div>
          </Link>

          <Link to="/portal/factories" className="portal-launcher-card portal-launcher-card-factories">
            <div className="portal-launcher-icon">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M2 20h20M4 20V4l8 6 8-6v16"></path>
              </svg>
            </div>
            <div className="portal-launcher-name">Factories Dept.</div>
            <div className="portal-launcher-desc">Dept. of Factories, Boilers, Industrial Safety & Health.</div>
            <div className="portal-launcher-tag">Department Portal</div>
          </Link>
        </div>

        <div className="portal-synckar-note">
          <span className="portal-synckar-badge">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" style={{display: 'inline-block', verticalAlign: 'middle', marginRight: 6}}>
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
            </svg>
            SYNCKAR ONLINE
          </span>
          <span>Changes made in any portal are automatically detected and propagated by the SyncKar middleware.</span>
          <Link to="/">RETURN TO DASHBOARD</Link>
        </div>
      </div>
    </div>
  )
}

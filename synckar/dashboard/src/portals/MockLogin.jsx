import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './portal.css'

export default function MockLogin() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const navigate = useNavigate()

  const handleLogin = (e) => {
    e.preventDefault()
    if (username.trim() && password.trim()) {
      sessionStorage.setItem('mock_logged_in', username)
      navigate('/portal')
    }
  }

  const quickLogin = (name) => {
    sessionStorage.setItem('mock_logged_in', name)
    navigate('/portal')
  }

  return (
    <div className="portal-login-root">
      <div className="portal-login-container">
        <div className="portal-login-header">
          <div className="portal-login-emblem">
            <svg aria-hidden="true" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <h1>Government of Karnataka</h1>
          <p>Single Sign-On for Department Officials</p>
        </div>

        <div className="portal-login-card">
          <form onSubmit={handleLogin} className="portal-login-form">
            <div className="portal-login-field">
              <label htmlFor="username">Officer ID / Username</label>
              <input
                id="username"
                type="text"
                className="portal-input"
                placeholder="e.g., KAS-0081"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="portal-login-field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                className="portal-input"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            
            <div className="portal-login-meta">
              <label className="portal-login-checkbox">
                <input type="checkbox" defaultChecked />
                <span>Remember me</span>
              </label>
              <a href="#" className="portal-login-forgot">Forgot Password?</a>
            </div>

            <button type="submit" className="portal-btn portal-btn-primary portal-login-submit">
              Sign In to Portals
            </button>
          </form>

          <div className="portal-login-divider">
            <span>OR QUICK DEMO LOGIN</span>
          </div>

          <div className="portal-login-quick">
            <button type="button" onClick={() => quickLogin('Officer Ramesh K.')} className="portal-btn-quick portal-btn-quick-sws">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"></rect></svg>
              SWS Administrator
            </button>
            <button type="button" onClick={() => quickLogin('Inspector Lakshmi N.')} className="portal-btn-quick portal-btn-quick-shop">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path></svg>
              Shop Inspector
            </button>
          </div>
        </div>
        
        <div className="portal-login-footer">
          <p>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
            Secured by Karnataka Authentication Service
          </p>
        </div>
      </div>
    </div>
  )
}

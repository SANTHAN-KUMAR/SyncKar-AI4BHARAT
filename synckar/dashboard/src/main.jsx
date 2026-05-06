import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import PortalSWS from './portals/PortalSWS.jsx'
import PortalShop from './portals/PortalShop.jsx'
import PortalFactories from './portals/PortalFactories.jsx'
import PortalLauncher from './portals/PortalLauncher.jsx'
import MockLogin from './portals/MockLogin.jsx'
import AuthGuard from './portals/AuthGuard.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter basename="/dashboard">
      <Routes>
        {/* Main SyncKar dashboard */}
        <Route path="/" element={<App />} />

        {/* Government department portals */}
        <Route path="/portal/login" element={<MockLogin />} />
        
        <Route path="/portal" element={<AuthGuard><PortalLauncher /></AuthGuard>} />
        <Route path="/portal/sws" element={<AuthGuard><PortalSWS /></AuthGuard>} />
        <Route path="/portal/shop" element={<AuthGuard><PortalShop /></AuthGuard>} />
        <Route path="/portal/factories" element={<AuthGuard><PortalFactories /></AuthGuard>} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)

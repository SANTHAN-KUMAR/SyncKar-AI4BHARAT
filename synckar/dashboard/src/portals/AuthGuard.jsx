import { Navigate } from 'react-router-dom'

export default function AuthGuard({ children }) {
  const user = sessionStorage.getItem('mock_logged_in')
  
  if (!user) {
    return <Navigate to="/portal/login" replace />
  }

  return children
}

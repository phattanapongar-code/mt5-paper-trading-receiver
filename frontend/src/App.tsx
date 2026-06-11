import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Overview from './pages/Overview'
import Charts from './pages/Charts'
import BotManager from './pages/BotManager'
import BotDetail from './pages/BotDetail'
import Compare from './pages/Compare'
import Signals from './pages/Signals'
import Performance from './pages/Performance'
import TradeHistory from './pages/TradeHistory'
import Wallets from './pages/Wallets'
import MarketStructure from './pages/MarketStructure'
import PendingOrders from './pages/PendingOrders'
import Settings from './pages/Settings'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-900">
        <div className="animate-pulse text-text-muted text-sm font-mono">Initializing...</div>
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppRoutes() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-900">
        <div className="animate-pulse text-text-muted text-sm font-mono">Initializing...</div>
      </div>
    )
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <Login />}
      />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Overview />} />
        <Route path="/charts" element={<Charts />} />
        <Route path="/bots" element={<BotManager />} />
        <Route path="/bots/:botId" element={<BotDetail />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/signals" element={<Signals />} />
        <Route path="/performance" element={<Performance />} />
        <Route path="/trades" element={<TradeHistory />} />
        <Route path="/wallets" element={<Wallets />} />
        <Route path="/market-structure" element={<MarketStructure />} />
        <Route path="/pending-orders" element={<PendingOrders />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}

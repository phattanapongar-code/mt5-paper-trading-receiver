import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import { lazy, Suspense } from 'react'

const Login = lazy(() => import('./pages/Login'))
const Overview = lazy(() => import('./pages/Overview'))
const Charts = lazy(() => import('./pages/Charts'))
const BotManager = lazy(() => import('./pages/BotManager'))
const BotDetail = lazy(() => import('./pages/BotDetail'))
const Compare = lazy(() => import('./pages/Compare'))
const Signals = lazy(() => import('./pages/Signals'))
const Performance = lazy(() => import('./pages/Performance'))
const TradeHistory = lazy(() => import('./pages/TradeHistory'))
const Trade = lazy(() => import('./pages/Trade'))
const Wallets = lazy(() => import('./pages/Wallets'))
const MarketStructure = lazy(() => import('./pages/MarketStructure'))
const PendingOrders = lazy(() => import('./pages/PendingOrders'))
const Settings = lazy(() => import('./pages/Settings'))

const LoadingFallback = () => (
  <div className="flex min-h-screen items-center justify-center bg-surface-900">
    <div className="animate-pulse text-text-muted text-sm font-mono">Loading...</div>
  </div>
)

function ProtectedRouteWrapper({ children }: { children: React.ReactNode }) {
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
        element={
          <Suspense fallback={<LoadingFallback />}>
            {isAuthenticated ? <Navigate to="/" replace /> : <Login />}
          </Suspense>
        }
      />
      <Route
        element={
          <Suspense fallback={<LoadingFallback />}>
            <ProtectedRouteWrapper>
              <Layout />
            </ProtectedRouteWrapper>
          </Suspense>
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
        <Route path="/trade" element={<Trade />} />
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

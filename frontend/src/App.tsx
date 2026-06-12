import { Component, type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { BotProvider } from './context/BotContext'
import { ThemeProvider } from './context/ThemeContext'
import Layout from './components/Layout'
import { ToastProvider } from './components/Toast'
import { lazy, Suspense } from 'react'

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-canvas-dark">
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-8 max-w-md text-center">
            <h1 className="text-lg font-semibold text-trading-down mb-2">Something went wrong</h1>
            <p className="text-sm text-muted mb-4 font-mono">{this.state.error?.message ?? 'Unknown error'}</p>
            <button onClick={() => { this.setState({ hasError: false, error: null }); window.location.href = '/' }}
              className="px-4 py-2 bg-primary/10 text-primary border border-primary/50 rounded-md text-sm cursor-pointer">
              Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

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
const MarketStructure = lazy(() => import('./pages/MarketStructure'))
const PendingOrders = lazy(() => import('./pages/PendingOrders'))
const Settings = lazy(() => import('./pages/Settings'))
const ReplayPage = lazy(() => import('./pages/Replay'))
const BacktestPage = lazy(() => import('./pages/Backtest'))
const BacktestOptimizePage = lazy(() => import('./pages/BacktestOptimize'))

const LoadingFallback = () => (
  <div className="flex min-h-screen items-center justify-center bg-canvas-dark">
    <div className="animate-pulse text-text-muted text-sm font-mono">Loading...</div>
  </div>
)

function ProtectedRouteWrapper({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas-dark">
        <div className="animate-pulse text-text-muted text-sm font-mono">Initializing...</div>
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <BotProvider>{children}</BotProvider>
}

function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas-dark">
      <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-8 max-w-md text-center">
        <h1 className="text-4xl font-bold text-primary mb-2">404</h1>
        <p className="text-sm text-muted mb-6">This page doesn't exist</p>
        <Link to="/" className="px-4 py-2 bg-primary/10 text-primary border border-primary/50 rounded-md text-sm">
          Back to Overview
        </Link>
      </div>
    </div>
  )
}

function AppRoutes() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas-dark">
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
        <Route path="/market-structure" element={<MarketStructure />} />
        <Route path="/pending-orders" element={<PendingOrders />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/replay" element={<ReplayPage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/backtest/optimize" element={<BacktestOptimizePage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <ToastProvider>
              <AppRoutes />
            </ToastProvider>
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

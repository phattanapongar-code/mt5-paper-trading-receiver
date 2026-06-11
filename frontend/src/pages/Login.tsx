import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
    } catch {
      setError('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas-dark">
      <div className="w-full max-w-sm px-6">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-primary font-mono tracking-wider">
            BINANCE
          </h1>
          <p className="text-sm text-muted mt-1">Paper Trading Receiver</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-2.5 bg-surface-card-dark border border-surface-400 rounded-lg text-body placeholder:text-muted focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 text-sm"
              autoFocus
            />
          </div>
          <div>
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2.5 bg-surface-card-dark border border-surface-400 rounded-lg text-body placeholder:text-muted focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 text-sm"
            />
          </div>

          {error && (
            <p className="text-trading-down text-xs text-center">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !username || !password}
            className="w-full py-2.5 bg-primary/10 border border-primary/50 text-primary rounded-lg text-sm font-semibold hover:bg-primary/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            {loading ? 'Connecting...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}

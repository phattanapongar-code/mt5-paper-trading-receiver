import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { setAuth, clearAuth, persistAuth, restoreAuth } from '../api/client'
import client from '../api/client'

interface AuthContextType {
  isAuthenticated: boolean
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const restored = restoreAuth()
    if (!restored) {
      setLoading(false)
      return
    }
    client.get('/state').then(() => {
      setIsAuthenticated(true)
    }).catch(() => {
      clearAuth()
    }).finally(() => {
      setLoading(false)
    })
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    setAuth(username, password)
    const res = await client.get('/state')
    if (res.status === 200) {
      persistAuth()
      setIsAuthenticated(true)
    }
  }, [])

  const logout = useCallback(() => {
    clearAuth()
    setIsAuthenticated(false)
  }, [])

  return (
    <AuthContext.Provider value={{ isAuthenticated, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

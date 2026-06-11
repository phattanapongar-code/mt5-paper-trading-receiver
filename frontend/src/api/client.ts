import axios from 'axios'

const STORAGE_KEY = 'mt5_dashboard_auth'

const client = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

let _auth: { username: string; password: string } | null = null

export function setAuth(username: string, password: string) {
  _auth = { username, password }
  const encoded = btoa(`${username}:${password}`)
  client.defaults.headers.common['Authorization'] = `Basic ${encoded}`
}

export function clearAuth() {
  _auth = null
  delete client.defaults.headers.common['Authorization']
  localStorage.removeItem(STORAGE_KEY)
}

export function hasAuth() {
  return _auth !== null
}

export function persistAuth() {
  if (_auth) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(_auth))
  }
}

export function restoreAuth(): boolean {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (!stored) return false
  try {
    const { username, password } = JSON.parse(stored)
    setAuth(username, password)
    return true
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return false
  }
}

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      clearAuth()
    }
    return Promise.reject(err)
  },
)

export default client

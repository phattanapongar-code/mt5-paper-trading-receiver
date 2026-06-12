import axios from 'axios'
import type { AxiosRequestConfig } from 'axios'

const STORAGE_KEY = 'mt5_dashboard_auth'

// Request cache: dedup GET requests with 2s TTL
const cache = new Map<string, { data: unknown; ts: number }>()
const CACHE_TTL = 2000

function cacheKey(url: string, params: Record<string, unknown> | undefined): string {
  if (!params || Object.keys(params).length === 0) return url
  const sorted = Object.keys(params).sort().map(k => `${k}=${String(params[k])}`).join('&')
  return `${url}?${sorted}`
}

const client = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// Only inject symbol param on endpoints that accept it
const SYMBOL_ENDPOINTS = [
  '/candles', '/indicators', '/swings', '/bos', '/order-blocks',
  '/market-structure', '/state', '/pending-orders/state',
]
client.interceptors.request.use((config: AxiosRequestConfig) => {
  if (_symbol && config.method?.toUpperCase() === 'GET') {
    const shouldInject = SYMBOL_ENDPOINTS.some(p => (config.url ?? '').startsWith(p))
    if (shouldInject) {
      const params = config.params ?? {}
      if (!params.symbol) {
        params.symbol = _symbol
        config.params = params
      }
    }
  }
  if (config.method?.toUpperCase() === 'GET') {
    const key = cacheKey(config.url ?? '', config.params as Record<string, unknown> | undefined)
    const hit = cache.get(key)
    if (hit && Date.now() - hit.ts < CACHE_TTL) {
      const source = axios.CancelToken.source()
      config.cancelToken = source.token
      source.cancel(JSON.stringify(hit.data))
    }
  }
  return config
})

client.interceptors.response.use(
  (res) => {
    const method = res.config.method?.toUpperCase()
    if (method === 'GET') {
      const key = cacheKey(res.config.url ?? '', res.config.params as Record<string, unknown> | undefined)
      cache.set(key, { data: res.data, ts: Date.now() })
    } else {
      cache.clear() // invalidate cache on any mutation
    }
    return res
  },
  (err) => {
    if (axios.isCancel(err) && err.message) {
      // Return cached data
      return Promise.resolve({ data: JSON.parse(err.message) })
    }
    if (err.response?.status === 401) {
      clearAuth()
    }
    return Promise.reject(err)
  },
)

export function clearCache() {
  cache.clear()
}

let _auth: { username: string; password: string } | null = null

// Default symbol injected into all requests unless overridden
let _symbol: string | null = null

export function setDefaultSymbol(s: string) {
  _symbol = s
}



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

export default client

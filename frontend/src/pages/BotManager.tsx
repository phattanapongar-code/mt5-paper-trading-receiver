import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'
import type { Profile, Bot } from '../types/api'
import ProfileForm from '../components/ProfileForm'
import BotForm from '../components/BotForm'

const log = (...args: unknown[]) => console.log('[BotManager]', ...args)

export default function BotManager() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [bots, setBots] = useState<Bot[]>([])
  const [loading, setLoading] = useState(true)
  const [showProfileForm, setShowProfileForm] = useState(false)
  const [showBotForm, setShowBotForm] = useState(false)
  const navigate = useNavigate()

  const fetchData = useCallback(async () => {
    try {
      const [profRes, botsRes] = await Promise.all([
        client.get<Profile[]>('/profiles'),
        client.get<Bot[]>('/bots'),
      ])
      setProfiles(profRes.data)
      setBots(botsRes.data)
    } catch (err) {
      log('fetch failed', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const toggleBot = useCallback(async (botId: number, enabled: boolean) => {
    await client.post(`/bots/${botId}/${enabled ? 'disable' : 'enable'}`)
    fetchData()
  }, [fetchData])

  const toggleProfile = useCallback(async (profileId: number, enabled: boolean) => {
    await client.post(`/profiles/${profileId}/${enabled ? 'disable' : 'enable'}`)
    fetchData()
  }, [fetchData])

  const deleteProfile = useCallback(async (profileId: number) => {
    if (!confirm('Delete this profile and all its bots?')) return
    await client.delete(`/profiles/${profileId}`)
    fetchData()
  }, [fetchData])

  const deleteBot = useCallback(async (botId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this bot?')) return
    await client.delete(`/bots/${botId}`)
    fetchData()
  }, [fetchData])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-pulse text-muted text-sm font-mono">Loading...</div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-body">Bot Manager</h1>
        <div className="flex gap-2">
          <button onClick={() => setShowBotForm(true)} className="px-3 py-1.5 text-xs bg-primary/10 text-primary border border-primary/50 rounded cursor-pointer">+ Bot</button>
          <button onClick={() => setShowProfileForm(true)} className="px-3 py-1.5 text-xs bg-primary/10 text-primary border border-primary/50 rounded cursor-pointer">+ Profile</button>
          <span className="text-xs text-muted font-mono self-center ml-2">{bots.length} bots · {profiles.length} profiles</span>
        </div>
      </div>

      {showProfileForm && <ProfileForm onClose={() => setShowProfileForm(false)} onCreated={fetchData} />}
      {showBotForm && <BotForm profiles={profiles} onClose={() => setShowBotForm(false)} onCreated={fetchData} />}

      {profiles.map((profile) => {
        const profileBots = bots.filter((b) => b.profile_id === profile.id)
        return (
          <div key={profile.id} className="bg-surface-card-dark border border-hairline-on-dark rounded-lg overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 bg-surface-elevated-dark/50 border-b border-hairline-on-dark">
              <div>
                <span className="text-sm font-semibold text-body">{profile.name}</span>
                {profile.description && (
                  <span className="text-xs text-muted ml-2">{profile.description}</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-muted font-mono">
                  ${profile.total_balance?.toFixed(2) ?? '0.00'}
                </span>
                <span className={`text-xs font-mono ${(profile.total_realized_pnl ?? 0) >= 0 ? 'text-trading-up' : 'text-trading-down'}`}>
                  {(profile.total_realized_pnl ?? 0) >= 0 ? '+' : ''}${profile.total_realized_pnl?.toFixed(2) ?? '0.00'}
                </span>
                <button onClick={() => deleteProfile(profile.id)}
                  className="px-2 py-1 text-xs text-rose-500 border border-rose-500/50 rounded bg-rose-500/10 cursor-pointer">Delete</button>
                <button onClick={() => toggleProfile(profile.id, !!profile.enabled)}
                  className={`px-2.5 py-1 text-xs rounded-md font-semibold transition-colors cursor-pointer ${
                    profile.enabled
                      ? 'bg-trading-up/10 text-trading-up border border-trading-up/50'
                      : 'bg-surface-elevated-dark text-muted border border-surface-400'
                  }`}>
                  {profile.enabled ? 'ENABLED' : 'DISABLED'}
                </button>
              </div>
            </div>

            {profileBots.length > 0 ? (
              <div className="divide-y divide-surface-elevated-dark">
                {profileBots.map((bot) => (
                  <div key={bot.id}
                    className="flex items-center justify-between px-4 py-3 hover:bg-surface-elevated-dark/30 cursor-pointer transition-colors"
                    onClick={() => navigate(`/bots/${bot.id}`)}>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-body">{bot.name}</span>
                      <span className="text-xs font-mono text-muted">{bot.strategy_type} v{bot.strategy_version}</span>
                      <span className="text-xs font-mono text-muted">{bot.symbol} {bot.timeframe}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={(e) => deleteBot(bot.id, e)}
                        className="px-2 py-1 text-xs text-rose-500 border border-rose-500/50 rounded bg-rose-500/10 cursor-pointer">Del</button>
                      <button onClick={(e) => { e.stopPropagation(); toggleBot(bot.id, !!bot.enabled) }}
                        className={`px-2.5 py-1 text-xs rounded-md font-semibold transition-colors cursor-pointer ${
                          bot.enabled
                            ? 'bg-trading-up/10 text-trading-up border border-trading-up/50'
                            : 'bg-surface-elevated-dark text-muted border border-surface-400'
                        }`}>
                        {bot.enabled ? 'ON' : 'OFF'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-4 py-6 text-center text-sm text-muted">No bots in this profile</div>
            )}
          </div>
        )
      })}

      {profiles.length === 0 && (
        <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-8 text-center">
          <p className="text-sm text-muted">No profiles found. Create one.</p>
        </div>
      )}
    </div>
  )
}

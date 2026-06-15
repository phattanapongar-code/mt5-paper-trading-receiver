import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'
import { useToast } from '../components/Toast'
import type { Profile, Bot, StrategyOption } from '../types/api'

const STRATEGY_COLORS: Record<string, string> = {
  trend_ob: '#FCD535',
}
import ProfileForm from '../components/ProfileForm'
import BotForm from '../components/BotForm'

interface EditBotState {
  bot: Bot
  name: string
  symbol: string
  timeframe: string
  strategy_type: string
}

function isLive(bot: Bot): boolean {
  if (!bot.runtime_updated_at) return false
  return Date.now() / 1000 - bot.runtime_updated_at < 10
}

export default function BotManager() {
  const { addToast } = useToast()
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [bots, setBots] = useState<Bot[]>([])
  const [loading, setLoading] = useState(true)
  const [showProfileForm, setShowProfileForm] = useState(false)
  const [showBotForm, setShowBotForm] = useState(false)
  const [editBot, setEditBot] = useState<EditBotState | null>(null)
  const [strategies, setStrategies] = useState<StrategyOption[]>([])
  const navigate = useNavigate()

  const fetchData = useCallback(async () => {
    try {
      const [profRes, botsRes, stratRes] = await Promise.all([
        client.get<Profile[]>('/profiles'),
        client.get<Bot[]>('/bots'),
        client.get<StrategyOption[]>('/strategies'),
      ])
      setProfiles(profRes.data)
      setBots(botsRes.data)
      setStrategies(stratRes.data)
    } catch {
      addToast('Failed to load bots', 'error')
    } finally {
      setLoading(false)
    }
  }, [addToast])

  const toggleBot = useCallback(async (botId: number, enabled: boolean) => {
    try {
      await client.post(`/bots/${botId}/${enabled ? 'disable' : 'enable'}`)
      fetchData()
    } catch { addToast('Failed to toggle bot', 'error') }
  }, [fetchData, addToast])

  const toggleProfile = useCallback(async (profileId: number, enabled: boolean) => {
    try {
      await client.post(`/profiles/${profileId}/${enabled ? 'disable' : 'enable'}`)
      fetchData()
    } catch { addToast('Failed to toggle profile', 'error') }
  }, [fetchData, addToast])

  const deleteProfile = useCallback(async (profileId: number) => {
    if (!confirm('Delete this profile and all its bots?')) return
    try {
      await client.delete(`/profiles/${profileId}`)
      addToast('Profile deleted', 'success')
      fetchData()
    } catch { addToast('Failed to delete profile', 'error') }
  }, [fetchData, addToast])

  const deleteBot = useCallback(async (botId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this bot?')) return
    try {
      await client.delete(`/bots/${botId}`)
      addToast('Bot deleted', 'success')
      fetchData()
    } catch { addToast('Failed to delete bot', 'error') }
  }, [fetchData, addToast])

  const saveEdit = useCallback(async () => {
    if (!editBot) return
    try {
      await client.put(`/bots/${editBot.bot.id}`, {
        name: editBot.name,
        symbol: editBot.symbol,
        timeframe: editBot.timeframe,
        strategy_type: editBot.strategy_type,
      })
      setEditBot(null)
      addToast('Bot updated', 'success')
      fetchData()
    } catch { addToast('Failed to update bot', 'error') }
  }, [editBot, fetchData, addToast])

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
                <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${
                  profile.enabled ? 'text-trading-up' : 'text-muted'
                }`}>
                  <span className={`w-2 h-2 rounded-full ${profile.enabled ? 'bg-trading-up' : 'bg-surface-400'}`} />
                  {profile.enabled ? 'ON' : 'OFF'}
                </span>
                <button onClick={() => toggleProfile(profile.id, !!profile.enabled)}
                  className="px-2.5 py-1 text-xs rounded-md font-semibold transition-colors cursor-pointer bg-primary/10 text-primary border border-primary/50 hover:bg-primary/20">
                  {profile.enabled ? 'DISABLE' : 'ENABLE'}
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
                      {bot.enabled && isLive(bot) && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-trading-up">
                          <span className="w-1.5 h-1.5 rounded-full bg-trading-up shadow-[0_0_4px_#0ecb81] animate-pulse" />
                          LIVE
                        </span>
                      )}
                      {bot.enabled && !isLive(bot) && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-muted">
                          <span className="w-1.5 h-1.5 rounded-full bg-surface-400" />
                          IDLE
                        </span>
                      )}
                      <span className="inline-block w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: STRATEGY_COLORS[bot.strategy_type] ?? '#707a8a' }} />
                      <span className="text-xs font-mono text-muted">{bot.strategy_type} v{bot.strategy_version}</span>
                      <span className="text-xs font-mono text-muted">{bot.symbol} {bot.timeframe}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={(e) => { e.stopPropagation(); setEditBot({ bot, name: bot.name, symbol: bot.symbol, timeframe: bot.timeframe, strategy_type: bot.strategy_type }) }}
                        className="px-2 py-1 text-xs text-primary border border-primary/50 rounded bg-primary/10 cursor-pointer">Edit</button>
                      <button onClick={(e) => deleteBot(bot.id, e)}
                        className="px-2 py-1 text-xs text-rose-500 border border-rose-500/50 rounded bg-rose-500/10 cursor-pointer">Del</button>
                      <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${
                        bot.enabled ? 'text-trading-up' : 'text-muted'
                      }`}>
                        <span className={`w-2 h-2 rounded-full ${bot.enabled ? 'bg-trading-up' : 'bg-surface-400'}`} />
                        {bot.enabled ? 'ON' : 'OFF'}
                      </span>
                      <button onClick={(e) => { e.stopPropagation(); toggleBot(bot.id, !!bot.enabled) }}
                        className="px-2.5 py-1 text-xs rounded-md font-semibold transition-colors cursor-pointer bg-primary/10 text-primary border border-primary/50 hover:bg-primary/20">
                        {bot.enabled ? 'DISABLE' : 'ENABLE'}
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

      {editBot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setEditBot(null)}>
          <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-5 w-full max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-sm font-semibold text-body mb-4">Edit Bot</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-muted mb-1">Name</label>
                <input value={editBot.name} onChange={(e) => setEditBot({ ...editBot, name: e.target.value })}
                  className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body focus:outline-none focus:border-primary" />
              </div>
              <div>
                <label className="block text-xs text-muted mb-1">Symbol</label>
                <input value={editBot.symbol} onChange={(e) => setEditBot({ ...editBot, symbol: e.target.value })}
                  className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body focus:outline-none focus:border-primary" />
              </div>
              <div>
                <label className="block text-xs text-muted mb-1">Timeframe</label>
                <select value={editBot.timeframe} onChange={(e) => setEditBot({ ...editBot, timeframe: e.target.value })}
                  className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body focus:outline-none focus:border-primary">
                  <option value="M1">M1</option>
                  <option value="M5">M5</option>
                  <option value="M15">M15</option>
                  <option value="H1">H1</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-muted mb-1">Strategy</label>
                <select value={editBot.strategy_type} onChange={(e) => setEditBot({ ...editBot, strategy_type: e.target.value })}
                  className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body focus:outline-none focus:border-primary">
                  {strategies.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button onClick={() => setEditBot(null)}
                className="px-3 py-1.5 text-xs rounded bg-surface-elevated-dark text-muted border border-hairline-on-dark cursor-pointer">Cancel</button>
              <button onClick={saveEdit}
                className="px-3 py-1.5 text-xs rounded bg-primary/10 text-primary border border-primary/50 cursor-pointer">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

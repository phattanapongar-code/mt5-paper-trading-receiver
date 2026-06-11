import { useState } from 'react'
import client from '../api/client'
import type { Profile } from '../types/api'

interface Props {
  profiles: Profile[]
  onClose: () => void
  onCreated: () => void
}

export default function BotForm({ profiles, onClose, onCreated }: Props) {
  const [profileId, setProfileId] = useState(profiles[0]?.id ?? 0)
  const [name, setName] = useState('')
  const [initialBalance, setInitialBalance] = useState('500')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await client.post('/bots', { profile_id: profileId, name, initial_balance: parseFloat(initialBalance) })
      onCreated()
      onClose()
    } catch {
      alert('Failed to create bot')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-surface-800 border border-surface-500 rounded-lg p-6 w-96" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-sm font-semibold text-text-primary mb-4">Create Bot</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <select value={profileId} onChange={(e) => setProfileId(Number(e.target.value))}
            className="w-full px-3 py-2 bg-surface-900 border border-surface-400 rounded text-sm text-text-primary focus:outline-none focus:border-cyber-cyan">
            {profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <input type="text" placeholder="Bot name" value={name} onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 bg-surface-900 border border-surface-400 rounded text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-cyber-cyan" required autoFocus />
          <input type="number" placeholder="Initial balance" value={initialBalance} onChange={(e) => setInitialBalance(e.target.value)}
            className="w-full px-3 py-2 bg-surface-900 border border-surface-400 rounded text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-cyber-cyan" min="1" step="0.01" />
          <div className="flex gap-2 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-3 py-1.5 text-xs bg-surface-700 text-text-secondary rounded border border-surface-500 cursor-pointer">Cancel</button>
            <button type="submit" disabled={saving || !name} className="px-3 py-1.5 text-xs bg-cyber-cyan/20 text-cyber-cyan rounded border border-cyber-cyan/50 disabled:opacity-40 cursor-pointer">{saving ? 'Saving...' : 'Create'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

import { useState } from 'react'
import client from '../api/client'

interface Props {
  onClose: () => void
  onCreated: () => void
}

export default function ProfileForm({ onClose, onCreated }: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await client.post('/profiles', { name, description })
      onCreated()
      onClose()
    } catch {
      alert('Failed to create profile')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-surface-card-dark border border-hairline-on-dark rounded-lg p-6 w-96" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-sm font-semibold text-body mb-4">Create Profile</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="text" placeholder="Profile name" value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body placeholder:text-muted focus:outline-none focus:border-primary"
            required autoFocus
          />
          <input
            type="text" placeholder="Description (optional)" value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3 py-2 bg-surface-elevated-dark border border-hairline-on-dark rounded text-sm text-body placeholder:text-muted focus:outline-none focus:border-primary"
          />
          <div className="flex gap-2 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-3 py-1.5 text-xs bg-surface-elevated-dark text-muted rounded border border-hairline-on-dark cursor-pointer">Cancel</button>
            <button type="submit" disabled={saving || !name} className="px-3 py-1.5 text-xs bg-primary/10 text-primary rounded border border-primary/50 disabled:opacity-40 cursor-pointer">{saving ? 'Saving...' : 'Create'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

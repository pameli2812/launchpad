import { useState } from 'react'
import {
  useApiKeys,
  useSetApiKey,
  useDeleteApiKey,
  useExtensionTokens,
  useCreateExtensionToken,
  useRevokeExtensionToken,
  type ApiKeyRow,
} from '@/hooks'
import type { LLMProvider } from '@/api/client'
import { Card } from '@/components/UI'
import {
  KeyRound, Trash2, Plus, Check, Copy, Sparkles, AlertTriangle, EyeOff,
} from 'lucide-react'

// ── Provider config ──────────────────────────────────────────────────────────

const PROVIDERS: {
  id: LLMProvider
  label: string
  blurb: string
  keyPrefix: string
  defaultModel: string
  modelHint: string
  iconColor: string
}[] = [
  {
    id: 'anthropic',
    label: 'Anthropic Claude',
    blurb: 'Primary in the default chain. Sonnet 4.6 is the recommended model.',
    keyPrefix: 'sk-ant-',
    defaultModel: 'claude-sonnet-4-6',
    modelHint: 'e.g. claude-sonnet-4-6, claude-haiku-4-5, claude-opus-4-7',
    iconColor: 'bg-orange-100 text-orange-600',
  },
  {
    id: 'openai',
    label: 'OpenAI',
    blurb: 'Secondary fallback. gpt-4o-mini is fast and cheap.',
    keyPrefix: 'sk-',
    defaultModel: 'gpt-4o-mini',
    modelHint: 'e.g. gpt-4o-mini, gpt-4o, gpt-4.1',
    iconColor: 'bg-emerald-100 text-emerald-600',
  },
  {
    id: 'gemini',
    label: 'Google Gemini',
    blurb: 'Optional. gemini-2.0-flash is fast and very cheap.',
    keyPrefix: '',
    defaultModel: 'gemini-2.0-flash',
    modelHint: 'e.g. gemini-2.0-flash, gemini-2.5-pro',
    iconColor: 'bg-sky-100 text-sky-600',
  },
]

// ── Model options per provider ────────────────────────────────────────────────

const MODEL_OPTIONS: Record<string, string[]> = {
  anthropic: [
    'claude-sonnet-4-6',
    'claude-haiku-4-5',
    'claude-opus-4-7',
  ],
  openai: [
    'gpt-4o-mini',
    'gpt-4o',
    'gpt-4.1',
  ],
  gemini: [
    'gemini-2.0-flash',
    'gemini-2.5-pro',
  ],
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function SettingsPage() {
  const { data: keys = [] } = useApiKeys()
  const keysByProvider: Record<string, ApiKeyRow> = {}
  for (const k of keys) keysByProvider[k.provider] = k

  return (
    <div className="max-w-5xl mx-auto p-8 space-y-10">
      <div className="border-b border-slate-200 pb-6">
        <h1 className="text-3xl font-bold text-slate-900">Settings</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Add your own LLM API keys and generate tokens for the browser extension.
        </p>
      </div>

      {/* ── API keys section ───────────────────────────────────────────────── */}
      <section>
        <div className="mb-4">
          <h2 className="text-xl font-bold text-slate-900">LLM API keys</h2>
          <p className="text-slate-500 text-sm mt-1">
            When set, your key takes precedence over the server's default for every analysis
            in your account. Keys are encrypted at rest with Fernet — only the last 4
            characters are ever shown back to you.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {PROVIDERS.map((p) => (
            <ProviderCard
              key={p.id}
              cfg={p}
              existing={keysByProvider[p.id] ?? null}
              isActive={keys.find(k => k.provider === p.id)?.is_active ?? false}
            />
          ))}
        </div>
      </section>

      {/* ── Extension tokens section ───────────────────────────────────────── */}
      <ExtensionTokensSection />
    </div>
  )
}

// ── Provider card ─────────────────────────────────────────────────────────────

function ProviderCard({
  cfg,
  existing,
  isActive,
}: {
  cfg: (typeof PROVIDERS)[number]
  existing: ApiKeyRow | null
  isActive: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [key, setKey] = useState('')
  const [model, setModel] = useState(existing?.model ?? cfg.defaultModel)
  const [showKey, setShowKey] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { mutate: setApiKey, isPending: saving } = useSetApiKey()
  const { mutate: deleteApiKey } = useDeleteApiKey()

  const isSet = !!existing

  const handleSave = () => {
    setError(null)
    if (key.trim().length < 8) {
      setError('Key looks too short')
      return
    }
    if (!model.trim()) {
      setError('Please select a model')
      return
    }
    setApiKey(
      { provider: cfg.id, api_key: key.trim(), model: model.trim() },
      {
        onSuccess: () => {
          setEditing(false)
          setKey('')
        },
        onError: (e: any) => {
          setError(e?.response?.data?.detail ?? e?.message ?? 'Save failed')
        },
      },
    )
  }

  const handleRemove = () => {
    if (!window.confirm(`Remove your ${cfg.label} key? Analysis will fall back to the server default (if configured).`)) return
    deleteApiKey(cfg.id)
  }

  return (
    <Card className="flex flex-col">
      <div className="flex items-start gap-3 mb-3">
        <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${cfg.iconColor}`}>
          <KeyRound className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-900 truncate">{cfg.label}</h3>
          <p className="text-xs text-slate-500 leading-snug mt-0.5">{cfg.blurb}</p>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          {isActive && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-700">
              <Sparkles className="w-3 h-3" />
              Active
            </span>
          )}
          {isSet && !editing && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-700">
              <Check className="w-3 h-3" />
              Set
            </span>
          )}
        </div>
      </div>

      {/* ── Display mode ── */}
      {isSet && !editing ? (
        <div className="space-y-3">
          <div className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono text-slate-700">
            {cfg.keyPrefix}••••{existing!.last_4}
          </div>
          {existing!.model && (
            <p className="text-xs text-slate-500">
              Model: <span className="font-mono text-slate-700">{existing!.model}</span>
            </p>
          )}
          <div className="flex gap-2">
            <button
              onClick={() => { setEditing(true); setKey(''); setModel(existing?.model ?? cfg.defaultModel); setError(null) }}
              className="flex-1 px-3 py-1.5 text-sm font-medium rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700"
            >
              Replace
            </button>
            <button
              onClick={handleRemove}
              aria-label={`Remove ${cfg.label} key`}
              className="px-3 py-1.5 text-sm font-medium rounded-lg bg-red-50 hover:bg-red-100 text-red-600"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      ) : (
        /* ── Edit / Add mode ── */
        <div className="space-y-3">
          <div className="relative">
            <input
              type={showKey ? 'text' : 'password'}
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder={`${cfg.keyPrefix}…`}
              className="w-full px-3 py-2 pr-10 border border-slate-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoComplete="off"
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 p-1"
              aria-label={showKey ? 'Hide key' : 'Show key'}
            >
              <EyeOff className="w-4 h-4" />
            </button>
          </div>
          
          {/* ── Model dropdown (NEW) ── */}
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="">Select a model...</option>
            {MODEL_OPTIONS[cfg.id]?.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={saving || !key.trim() || !model.trim()}
              className="flex-1 px-3 py-1.5 text-sm font-medium rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
            >
              {saving ? 'Saving…' : isSet ? 'Replace' : 'Save key'}
            </button>
            {isSet && (
              <button
                onClick={() => { setEditing(false); setKey(''); setModel(existing?.model ?? cfg.defaultModel); setError(null) }}
                className="px-3 py-1.5 text-sm font-medium rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}

// ── Extension tokens section ─────────────────────────────────────────────────

function ExtensionTokensSection() {
  const { data: tokens = [] } = useExtensionTokens()
  const { mutate: createToken, isPending: creating } = useCreateExtensionToken()
  const { mutate: revokeToken } = useRevokeExtensionToken()

  const [newToken, setNewToken] = useState<{ token: string; label: string } | null>(null)
  const [label, setLabel] = useState('Browser extension')
  const [copied, setCopied] = useState(false)

  const handleCreate = () => {
    createToken(label.trim() || 'Browser extension', {
      onSuccess: (data) => {
        setNewToken({ token: data.token, label: data.metadata.label })
        setLabel('Browser extension')
      },
    })
  }

  const handleCopy = async () => {
    if (!newToken) return
    try {
      await navigator.clipboard.writeText(newToken.token)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard blocked — user can still triple-click + copy manually
    }
  }

  const activeTokens = tokens.filter((t) => !t.revoked)
  const revokedTokens = tokens.filter((t) => t.revoked)

  return (
    <section>
      <div className="mb-4">
        <h2 className="text-xl font-bold text-slate-900">Browser extension tokens</h2>
        <p className="text-slate-500 text-sm mt-1">
          The Launchpad browser extension authenticates with a long-lived token. Generate one
          here, then paste it into the extension's settings. Tokens are shown only once.
        </p>
      </div>

      {/* ── One-time token display modal ── */}
      {newToken && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm"
          onClick={() => setNewToken(null)}
        >
          <div
            className="bg-white rounded-xl shadow-2xl max-w-lg w-[90%] mx-4 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 pt-6 pb-4">
              <div className="flex items-start gap-3 mb-2">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">Copy your token now</h3>
                  <p className="text-sm text-slate-500 mt-0.5">
                    This is the only time it will be displayed. After you close this dialog, you
                    can only see the last 4 characters.
                  </p>
                </div>
              </div>
              <div className="bg-slate-900 text-slate-100 rounded-lg p-3 mt-4 font-mono text-xs break-all">
                {newToken.token}
              </div>
              <p className="text-xs text-slate-400 mt-2">Label: {newToken.label}</p>
            </div>
            <div className="px-6 py-4 bg-slate-50 flex gap-2 justify-end border-t border-slate-200">
              <button
                onClick={handleCopy}
                className="px-4 py-2 rounded-lg font-medium bg-blue-600 hover:bg-blue-700 text-white inline-flex items-center gap-2"
              >
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copied ? 'Copied' : 'Copy to clipboard'}
              </button>
              <button
                onClick={() => setNewToken(null)}
                className="px-4 py-2 rounded-lg font-medium text-slate-700 bg-white border border-slate-300 hover:bg-slate-100"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Generate form ── */}
      <Card className="mb-4">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-xs font-medium text-slate-600 mb-1">Label</label>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Browser extension"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="px-4 py-2 rounded-lg font-medium bg-blue-600 hover:bg-blue-700 text-white inline-flex items-center gap-2 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            {creating ? 'Generating…' : 'Generate token'}
          </button>
        </div>
      </Card>

      {/* ── Token list ── */}
      {activeTokens.length === 0 && revokedTokens.length === 0 ? (
        <Card>
          <p className="text-slate-500 text-sm text-center py-4">
            <Sparkles className="w-5 h-5 inline mr-1 text-slate-400" />
            No tokens yet. Generate one above to connect the browser extension.
          </p>
        </Card>
      ) : (
        <div className="space-y-2">
          {activeTokens.map((t) => (
            <div
              key={t.id}
              className="bg-white border border-slate-200 rounded-lg p-3 flex items-center gap-3"
            >
              <div className="flex-1 min-w-0">
                <p className="font-medium text-slate-900 text-sm truncate">{t.label}</p>
                <p className="text-xs text-slate-500 mt-0.5 font-mono">
                  ········{t.last_4}
                </p>
              </div>
              <div className="text-xs text-slate-400 text-right">
                {t.last_used_at ? (
                  <>Last used {new Date(t.last_used_at).toLocaleDateString()}</>
                ) : (
                  <>Never used</>
                )}
              </div>
              <button
                onClick={() => {
                  if (window.confirm(`Revoke "${t.label}"? Any extension using it will stop working.`)) {
                    revokeToken(t.id)
                  }
                }}
                className="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50"
                aria-label="Revoke token"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
          {revokedTokens.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer text-slate-500 hover:text-slate-700 pt-2">
                {revokedTokens.length} revoked token{revokedTokens.length === 1 ? '' : 's'}
              </summary>
              <div className="space-y-2 mt-2 opacity-60">
                {revokedTokens.map((t) => (
                  <div key={t.id} className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                    <p className="font-medium text-slate-900 text-sm">
                      {t.label} <span className="text-slate-400 font-normal">(revoked)</span>
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5 font-mono">
                      ········{t.last_4}
                    </p>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </section>
  )
}

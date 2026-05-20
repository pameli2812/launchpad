import { useHistory, useDeleteHistoryEntry } from '@/hooks'
import { Button, Card } from '@/components/UI'
import { Trash2 } from 'lucide-react'

type HistoryEntry = {
  jd_id: string
  analyzed_at: string
  goal_set_name: string
  resume_id: string
  jd_title?: string
  company?: string
  overall_fit: number
  verdict: 'apply' | 'borderline' | 'skip' | string
  status: string
  suggestions?: any
}

const VERDICT_STYLES: Record<string, string> = {
  apply: 'bg-green-100 text-green-700',
  borderline: 'bg-amber-100 text-amber-700',
  skip: 'bg-red-100 text-red-700',
}

function formatDate(iso?: string) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString(undefined, {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function countSuggestions(s: any): number {
  if (!s) return 0
  if (Array.isArray(s)) return s.length
  return (
    (s.paraphrasing?.length ?? 0) +
    (s.missing?.length ?? 0) +
    (s.remove?.length ?? 0) +
    (s.polish?.length ?? 0)
  )
}

export function HistoryPage() {
  const { data: history = [], isLoading } = useHistory() as {
    data: HistoryEntry[]
    isLoading: boolean
  }
  const { mutate: deleteEntry } = useDeleteHistoryEntry()

  if (isLoading) {
    return <div className="max-w-6xl mx-auto p-8 text-slate-500">Loading history…</div>
  }

  const stats = {
    total: history.length,
    apply: history.filter((e) => e.verdict === 'apply').length,
    borderline: history.filter((e) => e.verdict === 'borderline').length,
    skip: history.filter((e) => e.verdict === 'skip').length,
  }

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      <div className="border-b border-slate-200 pb-6">
        <h1 className="text-3xl font-bold text-slate-900">Analysis History</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Every analysis you run is saved here automatically
        </p>
      </div>

      {history.length === 0 ? (
        <Card className="text-center p-12">
          <p className="text-slate-500">No analysis history yet</p>
          <p className="text-slate-400 text-sm mt-2">Run your first analysis to get started</p>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-4">
            <StatCard label="Total" value={stats.total} />
            <StatCard label="Strong Match" value={stats.apply} tone="green" />
            <StatCard label="Borderline" value={stats.borderline} tone="amber" />
            <StatCard label="Skipped" value={stats.skip} tone="red" />
          </div>

          <div className="space-y-3">
            {history.map((entry) => {
              const verdictClass = VERDICT_STYLES[entry.verdict] ?? 'bg-slate-100 text-slate-700'
              const suggCount = countSuggestions(entry.suggestions)
              return (
                <Card key={entry.jd_id} className="hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold text-slate-900 truncate">
                        {entry.jd_title || 'Untitled role'}
                        {entry.company && (
                          <span className="text-slate-500 font-normal"> @ {entry.company}</span>
                        )}
                      </h3>
                      <p className="text-slate-600 text-sm mt-1 truncate">
                        {entry.resume_id} · {entry.goal_set_name}
                      </p>
                      <p className="text-slate-400 text-xs mt-1">{formatDate(entry.analyzed_at)}</p>
                    </div>

                    <div className="flex items-center gap-4 flex-shrink-0">
                      <div className="text-right">
                        <div className="text-2xl font-bold text-blue-600">
                          {entry.overall_fit?.toFixed(1) ?? '—'}
                          <span className="text-sm text-slate-400">/10</span>
                        </div>
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs font-semibold capitalize ${verdictClass}`}
                        >
                          {entry.verdict}
                        </span>
                      </div>

                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => {
                          if (window.confirm('Delete this analysis from history?')) {
                            deleteEntry(entry.jd_id)
                          }
                        }}
                        aria-label="Delete history entry"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>

                  {suggCount > 0 && (
                    <p className="text-xs text-slate-500 mt-3 pt-3 border-t border-slate-100">
                      {suggCount} suggestion{suggCount === 1 ? '' : 's'} saved
                    </p>
                  )}
                </Card>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone?: 'green' | 'amber' | 'red'
}) {
  const toneClass =
    tone === 'green'
      ? 'text-green-600'
      : tone === 'amber'
        ? 'text-amber-600'
        : tone === 'red'
          ? 'text-red-600'
          : 'text-slate-900'
  return (
    <Card>
      <div className="text-xs font-semibold text-slate-500 uppercase">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${toneClass}`}>{value}</div>
    </Card>
  )
}

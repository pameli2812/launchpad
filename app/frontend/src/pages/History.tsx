import { useState, useMemo } from 'react'
import { useHistory, useDeleteHistoryEntry } from '@/hooks'
import { Card } from '@/components/UI'
import { ConfirmModal } from '@/components/ConfirmModal'
import { analyzeAPI } from '@/api/client'
import {
  Trash2, X, ChevronRight, ArrowLeft, Target, FileText,
  Lightbulb, CheckCircle, MinusCircle, AlertCircle,
  TrendingUp, Building2, Calendar, Download, Sparkles,
  Mail, User, BadgeCheck,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

type ScoreDetail  = { goal_id: string; dimension: string; score: number; remark: string }
type Gap          = { type: string; details: string; criticality: 'High' | 'Medium' | 'Low' }
type Scorecard    = { scores: ScoreDetail[]; overall_fit: number; verdict: string; summary: string; gaps: Array<Gap | string> }
type Suggestions  = { paraphrasing?: any[]; missing?: any[]; remove?: any[]; polish?: any[] }
type HistoryEntry = {
  jd_id: string; analyzed_at: string; goal_set_name: string; resume_id: string
  jd_title?: string; company?: string; overall_fit: number
  verdict: 'apply' | 'borderline' | 'skip' | string
  status: string; scorecard?: Scorecard; suggestions?: Suggestions
  jd_json?: any
}

// ── Constants ─────────────────────────────────────────────────────────────────

const VERDICT_META: Record<string, { badge: string; ring: string; bg: string; label: string; Icon: any }> = {
  apply:      { badge: 'bg-green-100 text-green-700 border border-green-200', ring: 'ring-green-400', bg: 'bg-green-50 border-green-200 text-green-800', label: 'Strong Match', Icon: CheckCircle },
  borderline: { badge: 'bg-amber-100 text-amber-700 border border-amber-200', ring: 'ring-amber-400', bg: 'bg-amber-50 border-amber-200 text-amber-800',  label: 'Borderline',   Icon: MinusCircle },
  skip:       { badge: 'bg-red-100   text-red-700   border border-red-200',   ring: 'ring-red-400',   bg: 'bg-red-50 border-red-200 text-red-800',         label: 'Skip',         Icon: AlertCircle },
}

const CRIT_STYLES: Record<string, string> = {
  High:   'bg-red-50 text-red-700 border border-red-200',
  Medium: 'bg-amber-50 text-amber-700 border border-amber-200',
  Low:    'bg-slate-100 text-slate-600 border border-slate-200',
}

const SUGG_BUCKETS = [
  { key: 'paraphrasing', label: 'Text Edits',  color: 'bg-blue-50 text-blue-700 border border-blue-200' },
  { key: 'missing',      label: 'Add Content', color: 'bg-green-50 text-green-700 border border-green-200' },
  { key: 'remove',       label: 'Remove',      color: 'bg-red-50 text-red-700 border border-red-200' },
  { key: 'polish',       label: 'Polish',      color: 'bg-purple-50 text-purple-700 border border-purple-200' },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso?: string) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString(undefined, { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' }) }
  catch { return iso }
}

function countSuggestions(s?: Suggestions): number {
  if (!s) return 0
  return (s.paraphrasing?.length ?? 0) + (s.missing?.length ?? 0) + (s.remove?.length ?? 0) + (s.polish?.length ?? 0)
}

function normalizeGap(g: Gap | string): Gap {
  if (typeof g === 'string') return { type: 'Skills Gap', details: g, criticality: 'Medium' }
  return g
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const color = score >= 7.5 ? 'bg-green-500' : score >= 5.5 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${(score/10)*100}%` }} />
      </div>
      <span className={`text-xs font-bold w-10 text-right ${score >= 7.5 ? 'text-green-600' : score >= 5.5 ? 'text-amber-600' : 'text-red-600'}`}>
        {score.toFixed(1)}/10
      </span>
    </div>
  )
}

function SuggestionBucket({ items, label, color }: { items: any[]; label: string; color: string }) {
  const [open, setOpen] = useState(false)
  if (!items?.length) return null
  return (
    <div className={`rounded-xl border overflow-hidden ${color}`}>
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold"
        onClick={() => setOpen(o => !o)}
      >
        <span>{label} ({items.length})</span>
        <ChevronRight className={`w-4 h-4 transition-transform ${open ? 'rotate-90' : ''}`} />
      </button>
      {open && (
        <div className="divide-y divide-white/40 border-t border-white/40">
          {items.map((item: any, i: number) => (
            <div key={i} className="px-4 py-3 text-xs space-y-1 bg-white/50">
              {item.section && <span className="font-semibold uppercase tracking-wide text-slate-500">{item.section}</span>}
              {item.original && <p className="text-red-700 line-through">{item.original}</p>}
              {item.improved && <p className="text-green-700">{item.improved}</p>}
              {item.what_to_add && <p className="text-slate-700">{item.what_to_add}</p>}
              {item.text && <p className="text-slate-700">{item.text}</p>}
              {item.reason && <p className="text-slate-500 italic">{item.reason}</p>}
              {item.why_it_matters && <p className="text-slate-500 italic">{item.why_it_matters}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Detail Panel ──────────────────────────────────────────────────────────────

function DetailPanel({ entry, onClose }: { entry: HistoryEntry; onClose: () => void }) {
  const vm = VERDICT_META[entry.verdict] ?? VERDICT_META.borderline
  const VIcon = vm.Icon
  const sc = entry.scorecard
  const sugg = entry.suggestions
  const suggCount = countSuggestions(sugg)
  const jd = entry.jd_json ?? {}

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* backdrop */}
      <div className="flex-1 bg-slate-900/50 backdrop-blur-sm" onClick={onClose} />

      {/* slide-in panel */}
      <div className="w-full max-w-2xl bg-white shadow-2xl overflow-y-auto flex flex-col">

        {/* sticky header */}
        <div className="sticky top-0 bg-white border-b border-slate-100 px-6 py-4 flex items-center gap-3 z-10 shadow-sm">
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors flex-shrink-0">
            <ArrowLeft className="w-5 h-5 text-slate-600" />
          </button>
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-bold text-slate-900 truncate">
              {entry.jd_title || 'Untitled role'}
              {entry.company && <span className="text-slate-400 font-normal"> @ {entry.company}</span>}
            </h2>
            <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1">
              <Calendar className="w-3 h-3" />{formatDate(entry.analyzed_at)}
            </p>
          </div>
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold ${vm.badge}`}>
            <VIcon className="w-3.5 h-3.5" />{vm.label}
          </span>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 flex-shrink-0">
            <X className="w-4 h-4 text-slate-400" />
          </button>
        </div>

        <div className="p-6 space-y-7">

          {/* ── Scores overview ── */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-blue-50 rounded-xl p-4 text-center border border-blue-100">
              <div className="text-3xl font-bold text-blue-600">{entry.overall_fit?.toFixed(1) ?? '—'}</div>
              <div className="text-xs text-blue-500 mt-0.5 font-medium">Overall Fit / 10</div>
            </div>
            <div className="bg-slate-50 rounded-xl p-4 text-center border border-slate-100">
              <div className="text-2xl font-bold text-slate-700">{sc?.gaps?.length ?? 0}</div>
              <div className="text-xs text-slate-500 mt-0.5">Gaps Found</div>
            </div>
            <div className="bg-slate-50 rounded-xl p-4 text-center border border-slate-100">
              <div className="text-2xl font-bold text-slate-700">{suggCount}</div>
              <div className="text-xs text-slate-500 mt-0.5">Suggestions</div>
            </div>
          </div>

          {/* ── Meta ── */}
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-500">
            <span className="flex items-center gap-1.5"><FileText className="w-3.5 h-3.5 text-slate-400" />{entry.resume_id}</span>
            <span className="flex items-center gap-1.5"><Target className="w-3.5 h-3.5 text-slate-400" />{entry.goal_set_name}</span>
            {jd.seniority && <span className="flex items-center gap-1.5"><TrendingUp className="w-3.5 h-3.5 text-slate-400" />{jd.seniority}</span>}
            {jd.location_policy && <span className="flex items-center gap-1.5"><Building2 className="w-3.5 h-3.5 text-slate-400" />{jd.location_policy}</span>}
          </div>

          {/* ── Outreach contact ── */}
          {(jd.verified_email || jd.recipient_type || jd.contact_name) && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-1.5">
                <Mail className="w-4 h-4 text-blue-500" /> Outreach Contact
              </h3>
              <div className="grid grid-cols-1 gap-3">
                {jd.verified_email && (
                  <div className="bg-blue-50 rounded-xl p-4 border border-blue-100 flex items-start gap-3">
                    <BadgeCheck className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-xs font-semibold text-blue-600 uppercase tracking-wide">Verified Email</p>
                      <p className="text-sm text-slate-700 mt-1 break-all">{jd.verified_email}</p>
                    </div>
                  </div>
                )}
                {jd.recipient_type && (
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 flex items-start gap-3">
                    <User className="w-4 h-4 text-slate-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Recipient Type</p>
                      <p className="text-sm text-slate-700 mt-1">{jd.recipient_type}</p>
                    </div>
                  </div>
                )}
                {jd.contact_name && (
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 flex items-start gap-3">
                    <User className="w-4 h-4 text-slate-500 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Contact Name</p>
                      <p className="text-sm text-slate-700 mt-1">{jd.contact_name}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── JD details ── */}
          {(jd.key_requirements?.length > 0 || jd.nice_to_have?.length > 0) && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Job Description Details</h3>
              <div className="grid grid-cols-1 gap-3">
                {jd.key_requirements?.length > 0 && (
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Key Requirements</p>
                    <ul className="space-y-1">
                      {jd.key_requirements.map((r: string, i: number) => (
                        <li key={i} className="text-sm text-slate-700 flex items-start gap-2">
                          <span className="text-blue-400 mt-0.5 flex-shrink-0">•</span>{r}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {jd.nice_to_have?.length > 0 && (
                  <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Nice to Have</p>
                    <ul className="space-y-1">
                      {jd.nice_to_have.map((r: string, i: number) => (
                        <li key={i} className="text-sm text-slate-700 flex items-start gap-2">
                          <span className="text-slate-400 mt-0.5 flex-shrink-0">•</span>{r}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Summary ── */}
          {sc?.summary && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-2">Analysis Summary</h3>
              <p className="text-sm text-slate-600 leading-relaxed bg-slate-50 rounded-xl p-4 border border-slate-100">
                {sc.summary}
              </p>
            </div>
          )}

          {/* ── Scorecard ── */}
          {sc?.scores && sc.scores.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Scorecard</h3>
              <div className="border border-slate-100 rounded-xl overflow-hidden">
                {sc.scores.map((s, i) => (
                  <div key={i} className={`px-4 py-3 ${i !== sc.scores.length - 1 ? 'border-b border-slate-100' : ''}`}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm font-semibold text-slate-800">{s.dimension}</span>
                    </div>
                    <ScoreBar score={s.score} />
                    {s.remark && <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{s.remark}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Gaps ── */}
          {sc?.gaps && sc.gaps.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Gaps to Address</h3>
              <div className="space-y-2">
                {sc.gaps.map((g, i) => {
                  const gap = normalizeGap(g as any)
                  return (
                    <div key={i} className="flex items-start gap-3 bg-slate-50 rounded-xl p-3 border border-slate-100">
                      <span className={`mt-0.5 px-2 py-0.5 rounded text-xs font-semibold flex-shrink-0 ${CRIT_STYLES[gap.criticality] ?? CRIT_STYLES.Medium}`}>
                        {gap.criticality}
                      </span>
                      <div>
                        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{gap.type}</span>
                        <p className="text-sm text-slate-700 mt-0.5">{gap.details}</p>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* ── Suggestions ── */}
          {sugg && suggCount > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-amber-500" />
                Saved Suggestions ({suggCount})
              </h3>
              <div className="space-y-2">
                {SUGG_BUCKETS.map(({ key, label, color }) => (
                  <SuggestionBucket
                    key={key}
                    items={(sugg as any)[key] ?? []}
                    label={label}
                    color={color}
                  />
                ))}
              </div>
            </div>
          )}

          {/* ── Resume versions ── */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">Resume Used</h3>
            <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-slate-700 min-w-0">
                <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
                <span className="truncate">{entry.resume_id}</span>
              </div>
              <a
                href={analyzeAPI.getDownloadUrl(entry.resume_id)}
                download={entry.resume_id}
                onClick={e => e.stopPropagation()}
                className="flex-shrink-0 ml-3 flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition-colors"
              >
                <Download className="w-3.5 h-3.5" />
                Download
              </a>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}

// ── Stat tile ─────────────────────────────────────────────────────────────────

type FilterType = 'all' | 'apply' | 'borderline' | 'skip'

function StatTile({ label, value, tone, active, onClick }: {
  label: string; value: number; tone?: 'green' | 'amber' | 'red'
  active?: boolean; onClick?: () => void
}) {
  const valueColor = tone === 'green' ? 'text-green-600' : tone === 'amber' ? 'text-amber-600' : tone === 'red' ? 'text-red-600' : 'text-slate-900'
  const ringColor  = tone === 'green' ? 'ring-green-400' : tone === 'amber' ? 'ring-amber-400' : tone === 'red' ? 'ring-red-400' : 'ring-blue-400'
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-left w-full rounded-xl p-4 bg-white border shadow-sm transition-all
        ${active ? `ring-2 ${ringColor} border-transparent shadow-md` : 'border-slate-200 hover:border-slate-300 hover:shadow-md'}`}
    >
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${valueColor}`}>{value}</div>
      {active && <div className="text-xs text-slate-400 mt-1">Click to clear filter</div>}
    </button>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function HistoryPage() {
  const { data: history = [], isLoading } = useHistory() as { data: HistoryEntry[]; isLoading: boolean }
  const { mutate: deleteEntry, isPending: deleting } = useDeleteHistoryEntry()
  const [filter, setFilter]                   = useState<FilterType>('all')
  const [selected, setSelected]               = useState<HistoryEntry | null>(null)
  const [pendingDelete, setPendingDelete]     = useState<HistoryEntry | null>(null)

  const confirmDelete = () => {
    if (!pendingDelete) return
    deleteEntry(pendingDelete.jd_id, {
      onSettled: () => setPendingDelete(null),
    })
  }

  const stats = useMemo(() => ({
    total:      history.length,
    apply:      history.filter(e => e.verdict === 'apply').length,
    borderline: history.filter(e => e.verdict === 'borderline').length,
    skip:       history.filter(e => e.verdict === 'skip').length,
  }), [history])

  const filtered = useMemo(() =>
    filter === 'all' ? history : history.filter(e => e.verdict === filter),
    [history, filter]
  )

  if (isLoading) return <div className="max-w-6xl mx-auto p-8 text-slate-500">Loading history…</div>

  return (
    <>
      {selected && <DetailPanel entry={selected} onClose={() => setSelected(null)} />}

      <div className="max-w-6xl mx-auto p-8 space-y-8">
        <div className="border-b border-slate-200 pb-6">
          <h1 className="text-3xl font-bold text-slate-900">Analysis History</h1>
          <p className="text-slate-500 mt-1 text-sm">Every analysis you run is saved here automatically</p>
        </div>

        {history.length === 0 ? (
          <Card>
            <div className="text-center py-12">
              <p className="text-slate-500">No analysis history yet</p>
              <p className="text-slate-400 text-sm mt-2">Run your first analysis to get started</p>
            </div>
          </Card>
        ) : (
          <>
            {/* ── Filter tiles ── */}
            <div className="grid grid-cols-4 gap-4">
              {([
                { key: 'all' as FilterType,       label: 'Total',        value: stats.total,      tone: undefined    },
                { key: 'apply' as FilterType,     label: 'Strong Match', value: stats.apply,      tone: 'green' as const  },
                { key: 'borderline' as FilterType, label: 'Borderline',  value: stats.borderline, tone: 'amber' as const  },
                { key: 'skip' as FilterType,      label: 'Skipped',      value: stats.skip,       tone: 'red' as const    },
              ]).map(({ key, label, value, tone }) => (
                <StatTile
                  key={key}
                  label={label}
                  value={value}
                  tone={tone}
                  active={filter === key}
                  onClick={() => setFilter(f => f === key ? 'all' : key)}
                />
              ))}
            </div>

            {/* active filter badge */}
            {filter !== 'all' && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-500">Filtered:</span>
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${VERDICT_META[filter]?.badge}`}>
                  {VERDICT_META[filter]?.label}
                  <button onClick={() => setFilter('all')}><X className="w-3 h-3" /></button>
                </span>
                <span className="text-xs text-slate-400">{filtered.length} result{filtered.length !== 1 ? 's' : ''}</span>
              </div>
            )}

            {/* ── List ── */}
            <div className="space-y-3">
              {filtered.length === 0 ? (
                <Card><div className="text-center py-8 text-slate-500">No {filter} analyses yet</div></Card>
              ) : filtered.map(entry => {
                const vm = VERDICT_META[entry.verdict] ?? { badge: 'bg-slate-100 text-slate-700', label: entry.verdict }
                const suggCount = countSuggestions(entry.suggestions)
                return (
                  <div
                    key={entry.jd_id}
                    onClick={() => setSelected(entry)}
                    className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md hover:border-blue-200 transition-all cursor-pointer group"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <h3 className="text-base font-semibold text-slate-900 truncate group-hover:text-blue-600 transition-colors">
                          {entry.jd_title || 'Untitled role'}
                          {entry.company && <span className="text-slate-400 font-normal"> @ {entry.company}</span>}
                        </h3>
                        <p className="text-slate-500 text-sm mt-0.5 truncate">{entry.resume_id} · {entry.goal_set_name}</p>
                        <p className="text-slate-400 text-xs mt-0.5">{formatDate(entry.analyzed_at)}</p>
                        {suggCount > 0 && (
                          <p className="text-xs text-amber-600 mt-1.5 flex items-center gap-1">
                            <Lightbulb className="w-3 h-3" />
                            {suggCount} suggestion{suggCount !== 1 ? 's' : ''} saved
                          </p>
                        )}
                      </div>

                      <div className="flex items-center gap-3 flex-shrink-0">
                        <div className="text-right">
                          <div className="text-2xl font-bold text-blue-600">
                            {entry.overall_fit?.toFixed(1) ?? '—'}
                            <span className="text-sm text-slate-400 font-normal">/10</span>
                          </div>
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold mt-0.5 ${vm.badge}`}>
                            {vm.label}
                          </span>
                        </div>
                        <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-blue-400 transition-colors" />
                        <button
                          onClick={e => {
                            e.stopPropagation()
                            setPendingDelete(entry)
                          }}
                          className="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                          aria-label="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </>
        )}
      </div>

      <ConfirmModal
        open={!!pendingDelete}
        title="Delete this analysis?"
        message={
          pendingDelete ? (
            <>
              Permanently remove the analysis for{' '}
              <strong>{pendingDelete.jd_title || 'this role'}</strong>
              {pendingDelete.company ? ` @ ${pendingDelete.company}` : ''}? This cannot be undone.
            </>
          ) : (
            ''
          )
        }
        confirmLabel="Delete"
        variant="danger"
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  )
}
import { useEffect, useMemo, useState } from 'react'
import {
  useResumes,
  useGoalSets,
  useRunAnalysis,
  useGetSuggestions,
  useApplySuggestions,
} from '@/hooks'
import { analyzeAPI } from '@/api/client'
import { Button, Card } from '@/components/UI'
import { useAppStore } from '@/store'
import {
  Play,
  AlertCircle,
  CheckCircle,
  Sparkles,
  RefreshCw,
  RotateCcw,
  Download,
  FileCheck,
} from 'lucide-react'

type Resume = { name: string; size: number; modified: string }
type GoalSet = { id: string; name: string; goals: any[]; is_active?: boolean }
type Score = { goal_id: string; dimension: string; score: number; remark: string }
type Gap = { type: string; details: string; criticality: 'High' | 'Medium' | 'Low' }
type Scorecard = {
  scores: Score[]
  overall_fit: number
  verdict: 'apply' | 'borderline' | 'skip'
  summary: string
  gaps: Array<Gap | string>
}
type AnalysisResult = {
  jd_id: string
  jd: any
  scorecard: Scorecard
  resume_name: string
  goal_set_id: string
  goal_set_name: string
}
type Suggestions = {
  paraphrasing?: any[]
  missing?: any[]
  remove?: any[]
  polish?: any[]
}

const VERDICT_COPY = {
  apply: {
    text: 'Strong match — recommended to apply with your current resume.',
    className: 'bg-green-50 border-green-200 text-green-800',
    Icon: CheckCircle,
  },
  borderline: {
    text: 'Borderline match — address the gaps before applying.',
    className: 'bg-amber-50 border-amber-200 text-amber-800',
    Icon: AlertCircle,
  },
  skip: {
    text: 'Weak match — significant gaps exist.',
    className: 'bg-red-50 border-red-200 text-red-800',
    Icon: AlertCircle,
  },
} as const

export function AnalyzePage() {
  const setCurrentTab = useAppStore((s) => s.setCurrentTab)
  const { data: resumes = [], isLoading: resumesLoading } = useResumes() as { data: Resume[]; isLoading: boolean }
  const { data: goalSets = [], isLoading: goalsLoading } = useGoalSets() as { data: GoalSet[]; isLoading: boolean }

  const [selectedResume, setSelectedResume] = useState('')
  const [selectedGoalSet, setSelectedGoalSet] = useState('')
  const [jdText, setJdText] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [suggestions, setSuggestions] = useState<Suggestions | null>(null)
  const [userPrompt, setUserPrompt] = useState('')
  const [forceSuggestions, setForceSuggestions] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { mutate: runAnalysis, isPending: analyzing } = useRunAnalysis()
  const { mutate: getSuggestions, isPending: suggesting } = useGetSuggestions()

  // Default the resume + goal set selectors once data loads
  useEffect(() => {
    if (!selectedResume && resumes.length > 0) {
      setSelectedResume(resumes[0].name)
    }
  }, [resumes, selectedResume])

  useEffect(() => {
    if (!selectedGoalSet && goalSets.length > 0) {
      const active = goalSets.find((g) => g.is_active)
      setSelectedGoalSet((active ?? goalSets[0]).id)
    }
  }, [goalSets, selectedGoalSet])

  const handleRunAnalysis = () => {
    setError(null)
    if (!selectedResume || !selectedGoalSet || !jdText.trim()) {
      setError('Pick a resume, a goal set, and paste a job description.')
      return
    }
    runAnalysis(
      { resumeName: selectedResume, goalSetId: selectedGoalSet, jdText },
      {
        onSuccess: (data) => {
          setResult(data as AnalysisResult)
          setSuggestions(null)
          setForceSuggestions(false)
        },
        onError: (e: any) => {
          setError(e?.response?.data?.detail ?? e?.message ?? 'Analysis failed')
        },
      },
    )
  }

  const handleGetSuggestions = (override = false) => {
    if (!result) return
    getSuggestions(
      {
        resumeName: result.resume_name,
        jdJson: result.jd,
        gaps: result.scorecard.gaps,
        userPrompt: userPrompt.trim() || undefined,
        override,
      },
      {
        onSuccess: (data) => setSuggestions(data as Suggestions),
      },
    )
  }

  const handleStartNew = () => {
    setResult(null)
    setSuggestions(null)
    setUserPrompt('')
    setJdText('')
    setForceSuggestions(false)
    setError(null)
  }

  const showSuggestions =
    !!result && (result.scorecard.verdict !== 'skip' || forceSuggestions)

  // ── Empty states ──────────────────────────
  if (resumesLoading || goalsLoading) {
    return <div className="max-w-6xl mx-auto p-8 text-slate-500">Loading…</div>
  }

  if (resumes.length === 0 || goalSets.length === 0) {
    return (
      <div className="max-w-6xl mx-auto p-8">
        <Card className="text-center p-12">
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Finish setup first</h2>
          <p className="text-slate-500 mb-6">
            You need at least one resume and one goal set before you can analyze a job description.
          </p>
          <div className="text-sm text-slate-600 mb-6 space-y-1">
            <div>{resumes.length === 0 ? '✗' : '✓'} Resume uploaded</div>
            <div>{goalSets.length === 0 ? '✗' : '✓'} Goal set created</div>
          </div>
          <Button onClick={() => setCurrentTab('setup')}>Go to Setup</Button>
        </Card>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      <div className="flex justify-between items-end border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Analyze</h1>
          <p className="text-slate-500 mt-1 text-sm">
            Score your resume against a job description using your active goals
          </p>
        </div>
        {result && (
          <Button variant="secondary" onClick={handleStartNew}>
            <RotateCcw className="w-4 h-4 inline mr-2" />
            Start New Analysis
          </Button>
        )}
      </div>

      {!result ? (
        <Card>
          <h2 className="text-xl font-semibold text-slate-900 mb-6">New Analysis</h2>
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">📄 Resume</label>
              <select
                value={selectedResume}
                onChange={(e) => setSelectedResume(e.target.value)}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                {resumes.map((r) => (
                  <option key={r.name} value={r.name}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">🎯 Goal Set</label>
              <select
                value={selectedGoalSet}
                onChange={(e) => setSelectedGoalSet(e.target.value)}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                {goalSets.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                    {g.is_active ? ' (Active)' : ''} — {g.goals?.length ?? 0} metrics
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Job Description
              </label>
              <textarea
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                placeholder="Paste the full job description here…"
                rows={10}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
                {error}
              </div>
            )}

            <Button onClick={handleRunAnalysis} loading={analyzing} className="w-full">
              <Play className="w-4 h-4 inline mr-2" />
              Run Analysis
            </Button>
          </div>
        </Card>
      ) : (
        <AnalysisResults
          result={result}
          suggestions={suggestions}
          suggesting={suggesting}
          userPrompt={userPrompt}
          onUserPromptChange={setUserPrompt}
          onGetSuggestions={() => handleGetSuggestions(false)}
          onRegenerate={() => handleGetSuggestions(forceSuggestions)}
          showSuggestions={showSuggestions}
          onProceedAnyway={() => {
            setForceSuggestions(true)
            handleGetSuggestions(true)
          }}
          onStartNew={handleStartNew}
        />
      )}
    </div>
  )
}

/* ─────────────────────────────────────────────
   Results
   ───────────────────────────────────────────── */

function AnalysisResults({
  result,
  suggestions,
  suggesting,
  userPrompt,
  onUserPromptChange,
  onGetSuggestions,
  onRegenerate,
  showSuggestions,
  onProceedAnyway,
  onStartNew,
}: {
  result: AnalysisResult
  suggestions: Suggestions | null
  suggesting: boolean
  userPrompt: string
  onUserPromptChange: (v: string) => void
  onGetSuggestions: () => void
  onRegenerate: () => void
  showSuggestions: boolean
  onProceedAnyway: () => void
  onStartNew: () => void
}) {
  const { scorecard, jd } = result
  const verdict = VERDICT_COPY[scorecard.verdict] ?? VERDICT_COPY.borderline
  const VerdictIcon = verdict.Icon

  const [accepted, setAccepted] = useState<Set<number>>(new Set())
  const [revised, setRevised] = useState<{
    filename: string
    applied_count: number
    skipped_count: number
    skipped: any[]
  } | null>(null)
  const [applyError, setApplyError] = useState<string | null>(null)
  const { mutate: applySuggestions, isPending: applying } = useApplySuggestions()

  const allRows = useMemo(
    () => (suggestions ? suggestionsToRows(suggestions) : []),
    [suggestions],
  )

  // Reset the approval state whenever a fresh batch of suggestions arrives.
  useEffect(() => {
    setAccepted(new Set())
    setRevised(null)
    setApplyError(null)
  }, [suggestions])

  const toggleRow = (idx: number) => {
    setAccepted((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const selectAll = () => setAccepted(new Set(allRows.map((_, i) => i)))
  const clearAll = () => setAccepted(new Set())

  const handleApply = () => {
    setApplyError(null)
    const acceptedChanges = allRows
      .filter((_, idx) => accepted.has(idx))
      .map((row) => ({
        type: row.type,
        section: row.section,
        before: row.before,
        after: row.after,
      }))
    if (acceptedChanges.length === 0) return
    applySuggestions(
      { resumeName: result.resume_name, acceptedChanges },
      {
        onSuccess: (data: any) => {
          setRevised({
            filename: data.revised_filename,
            applied_count: data.report?.applied_count ?? acceptedChanges.length,
            skipped_count: data.report?.skipped_count ?? 0,
            skipped: data.report?.skipped ?? [],
          })
        },
        onError: (e: any) => {
          setApplyError(e?.response?.data?.detail ?? e?.message ?? 'Failed to apply changes')
        },
      },
    )
  }

  return (
    <div className="space-y-6">
      {/* Top metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-xs font-semibold text-slate-500 uppercase">Overall Fit</div>
          <div className="text-3xl font-bold text-blue-600 mt-1">
            {scorecard.overall_fit.toFixed(1)}<span className="text-lg text-slate-400">/10</span>
          </div>
        </Card>
        <Card>
          <div className="text-xs font-semibold text-slate-500 uppercase">Verdict</div>
          <div className="text-2xl font-bold text-slate-900 mt-1 capitalize">{scorecard.verdict}</div>
        </Card>
        <Card>
          <div className="text-xs font-semibold text-slate-500 uppercase">Role</div>
          <div className="text-base font-semibold text-slate-900 mt-1 truncate" title={jd.title}>
            {jd.title || '—'}
          </div>
          <div className="text-sm text-slate-500 truncate" title={jd.company}>
            {jd.company || '—'}
          </div>
        </Card>
        <Card>
          <div className="text-xs font-semibold text-slate-500 uppercase">Goal Set</div>
          <div className="text-base font-semibold text-slate-900 mt-1 truncate">
            {result.goal_set_name}
          </div>
        </Card>
      </div>

      {/* Verdict banner */}
      <div className={`flex items-start gap-3 border rounded-lg p-4 ${verdict.className}`}>
        <VerdictIcon className="w-5 h-5 mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <p className="font-medium">{verdict.text}</p>
          {scorecard.verdict === 'skip' && !showSuggestions && (
            <button
              onClick={onProceedAnyway}
              className="text-sm underline mt-1 font-medium"
            >
              Proceed anyway and get suggestions
            </button>
          )}
        </div>
      </div>

      {/* Summary */}
      <Card>
        <h3 className="text-lg font-semibold text-slate-900 mb-3">Summary</h3>
        <p className="text-slate-700 leading-relaxed">{scorecard.summary || '—'}</p>
      </Card>

      {/* Scorecard */}
      <Card>
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Scorecard</h3>
        <ScorecardTable scores={scorecard.scores} />
      </Card>

      {/* Gaps */}
      <Card>
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Gaps to Address</h3>
        <GapsList gaps={scorecard.gaps} />
      </Card>

      {/* Suggestions */}
      {showSuggestions && (
        <Card>
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-lg font-semibold text-slate-900">Resume Change Suggestions</h3>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Guide the suggestions <span className="text-slate-400">(optional)</span>
            </label>
            <textarea
              value={userPrompt}
              onChange={(e) => onUserPromptChange(e.target.value)}
              placeholder="e.g. Emphasize my AI experience. Keep changes concise. Make the leadership impact clearer."
              rows={2}
              className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex gap-2 mb-6">
            {!suggestions ? (
              <Button onClick={onGetSuggestions} loading={suggesting}>
                <Sparkles className="w-4 h-4 inline mr-2" />
                Get Suggestions
              </Button>
            ) : (
              <Button onClick={onRegenerate} loading={suggesting} variant="secondary">
                <RefreshCw className="w-4 h-4 inline mr-2" />
                Regenerate
              </Button>
            )}
          </div>

          {suggestions && allRows.length > 0 && (
            <>
              <div className="flex items-center justify-between mb-3 text-sm">
                <p className="text-slate-600">
                  Tick the changes you want applied to your resume.{' '}
                  <span className="font-medium text-slate-900">
                    {accepted.size} of {allRows.length}
                  </span>{' '}
                  selected.
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={selectAll}
                    className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                  >
                    Select all
                  </button>
                  <span className="text-slate-300">·</span>
                  <button
                    onClick={clearAll}
                    className="text-slate-600 hover:text-slate-700 text-sm font-medium"
                  >
                    Clear
                  </button>
                </div>
              </div>

              <SuggestionsTable
                rows={allRows}
                acceptedIndices={accepted}
                onToggle={toggleRow}
              />

              {applyError && (
                <div className="mt-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
                  {applyError}
                </div>
              )}

              <div className="mt-6 flex flex-wrap items-center gap-3">
                <Button
                  onClick={handleApply}
                  loading={applying}
                  disabled={accepted.size === 0 || applying}
                >
                  <FileCheck className="w-4 h-4 inline mr-2" />
                  Apply approved changes to PDF
                </Button>

                {revised && (
                  <a
                    href={analyzeAPI.getDownloadUrl(revised.filename)}
                    download={revised.filename}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600 text-white font-medium hover:bg-green-700"
                  >
                    <Download className="w-4 h-4" />
                    Download revised resume
                  </a>
                )}
              </div>

              {revised && (
                <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4 text-sm space-y-1">
                  <p className="text-green-900 font-medium">
                    Saved as <code className="font-mono">{revised.filename}</code> — it’s also
                    available in your Resume library.
                  </p>
                  <p className="text-green-800">
                    Applied {revised.applied_count} change
                    {revised.applied_count === 1 ? '' : 's'}.
                    {revised.skipped_count > 0 && (
                      <>
                        {' '}
                        Skipped {revised.skipped_count} — the original text couldn’t be located in
                        the PDF (often happens when text spans line breaks).
                      </>
                    )}
                  </p>
                  {revised.skipped.length > 0 && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-green-800 font-medium">
                        Show skipped changes
                      </summary>
                      <ul className="mt-2 space-y-1 list-disc list-inside text-green-900">
                        {revised.skipped.map((s: any, i: number) => (
                          <li key={i}>
                            <span className="font-medium">{s.type}</span> ({s.section || '—'}):{' '}
                            {s.reason}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              )}
            </>
          )}

          {suggestions && allRows.length === 0 && (
            <div className="text-sm text-slate-500 bg-slate-50 border border-slate-200 rounded-lg p-4">
              No structured suggestions returned. Try regenerating with a different prompt.
            </div>
          )}
        </Card>
      )}

      {/* Close the loop */}
      <Card>
        <h3 className="text-lg font-semibold text-slate-900 mb-1">Wrap up</h3>
        <p className="text-slate-500 text-sm mb-4">
          This analysis has been saved to your History automatically. When you're done, start a new one.
        </p>
        <Button onClick={onStartNew}>
          <RotateCcw className="w-4 h-4 inline mr-2" />
          Start New Analysis
        </Button>
      </Card>
    </div>
  )
}

/* ─────────────────────────────────────────────
   Sub-components
   ───────────────────────────────────────────── */

function ScorecardTable({ scores }: { scores: Score[] }) {
  if (!scores || scores.length === 0) {
    return <p className="text-slate-500 text-sm">No scores returned.</p>
  }
  const sorted = [...scores].sort((a, b) => b.score - a.score)
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <div className="grid grid-cols-[2fr_auto_auto_3fr] bg-slate-100 border-b border-slate-200 text-sm font-semibold text-slate-900">
        <div className="p-3">Dimension</div>
        <div className="p-3 text-center">Score</div>
        <div className="p-3 text-center">Level</div>
        <div className="p-3">Remarks</div>
      </div>
      {sorted.map((s) => {
        const level = s.score >= 8 ? 'High' : s.score >= 6 ? 'Mid' : 'Low'
        const levelColor =
          level === 'High'
            ? 'bg-green-100 text-green-700'
            : level === 'Mid'
              ? 'bg-amber-100 text-amber-700'
              : 'bg-red-100 text-red-700'
        return (
          <div
            key={s.goal_id}
            className="grid grid-cols-[2fr_auto_auto_3fr] border-b border-slate-200 last:border-b-0 text-sm"
          >
            <div className="p-3 font-medium text-slate-900">{s.dimension}</div>
            <div className="p-3 text-center text-slate-900 font-semibold">
              {s.score.toFixed(1)}/10
            </div>
            <div className="p-3 text-center">
              <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${levelColor}`}>
                {level}
              </span>
            </div>
            <div className="p-3 text-slate-600">{s.remark}</div>
          </div>
        )
      })}
    </div>
  )
}

const CRITICALITY_STYLES: Record<string, { bg: string; border: string; text: string; pill: string }> = {
  High: {
    bg: 'bg-red-50',
    border: 'border-red-200',
    text: 'text-red-900',
    pill: 'bg-red-600 text-white',
  },
  Medium: {
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    text: 'text-amber-900',
    pill: 'bg-amber-500 text-white',
  },
  Low: {
    bg: 'bg-green-50',
    border: 'border-green-200',
    text: 'text-green-900',
    pill: 'bg-green-600 text-white',
  },
}

function normalizeGap(g: Gap | string): Gap {
  if (typeof g === 'string') {
    const lower = g.toLowerCase()
    const criticality: Gap['criticality'] =
      /required|must|essential|critical/.test(lower)
        ? 'High'
        : /nice|preferred|bonus|plus/.test(lower)
          ? 'Low'
          : 'Medium'
    return { type: 'Skills Gap', details: g, criticality }
  }
  return {
    type: g.type || 'Skills Gap',
    details: g.details,
    criticality: (g.criticality as Gap['criticality']) || 'Medium',
  }
}

function GapsList({ gaps }: { gaps: Array<Gap | string> }) {
  const normalized = useMemo(() => (gaps ?? []).map(normalizeGap), [gaps])

  if (normalized.length === 0) {
    return (
      <div className="flex items-start gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
        <CheckCircle className="w-5 h-5 text-green-600 mt-0.5" />
        <div>
          <p className="font-medium text-green-900">No gaps found.</p>
          <p className="text-sm text-green-700">
            This JD is a strong match for the resume you selected — no resume-edit gaps were
            identified.
          </p>
        </div>
      </div>
    )
  }

  // Group by type so the user sees: "Skills Gap → [list]" with criticality on each item
  const byType: Record<string, Gap[]> = {}
  for (const gap of normalized) {
    ;(byType[gap.type] ??= []).push(gap)
  }

  return (
    <div className="space-y-5">
      {Object.entries(byType).map(([type, items]) => (
        <div key={type}>
          <h4 className="font-semibold text-slate-900 mb-2">{type}</h4>
          <div className="space-y-2">
            {items.map((g, i) => {
              const s = CRITICALITY_STYLES[g.criticality] ?? CRITICALITY_STYLES.Medium
              return (
                <div
                  key={i}
                  className={`flex items-start justify-between gap-4 border rounded-lg px-4 py-3 ${s.bg} ${s.border}`}
                >
                  <p className={`text-sm ${s.text} flex-1`}>{g.details}</p>
                  <span
                    className={`text-xs font-semibold px-2.5 py-1 rounded-full flex-shrink-0 ${s.pill}`}
                  >
                    {g.criticality}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

type SuggestionRow = {
  type: 'Text Edit' | 'Add Data' | 'Remove Text' | 'Polish Content'
  section: string
  before: string
  after: string
}

const TYPE_STYLES: Record<SuggestionRow['type'], { pill: string; header: string }> = {
  'Text Edit': { pill: 'bg-blue-100 text-blue-700', header: 'bg-blue-50' },
  'Add Data': { pill: 'bg-green-100 text-green-700', header: 'bg-green-50' },
  'Remove Text': { pill: 'bg-red-100 text-red-700', header: 'bg-red-50' },
  'Polish Content': { pill: 'bg-amber-100 text-amber-700', header: 'bg-amber-50' },
}

function suggestionsToRows(s: Suggestions): SuggestionRow[] {
  const rows: SuggestionRow[] = []
  for (const p of s.paraphrasing ?? []) {
    rows.push({
      type: 'Text Edit',
      section: p.section ?? '—',
      before: p.original ?? '—',
      after: p.improved ?? '—',
    })
  }
  for (const m of s.missing ?? []) {
    rows.push({
      type: 'Add Data',
      section: m.section ?? '—',
      before: 'No change',
      after: m.what_to_add ?? '—',
    })
  }
  for (const r of s.remove ?? []) {
    rows.push({
      type: 'Remove Text',
      section: r.section ?? '—',
      before: r.text ?? '—',
      after: 'Remove this content',
    })
  }
  for (const po of s.polish ?? []) {
    rows.push({
      type: 'Polish Content',
      section: po.section ?? '—',
      before: po.original ?? '—',
      after: po.improved ?? '—',
    })
  }
  return rows
}

function SuggestionsTable({
  rows,
  acceptedIndices,
  onToggle,
}: {
  rows: SuggestionRow[]
  acceptedIndices: Set<number>
  onToggle: (idx: number) => void
}) {
  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <div className="grid grid-cols-[40px_140px_140px_1fr_1fr] bg-slate-100 border-b border-slate-200 text-sm font-semibold text-slate-900">
        <div className="p-3 text-center">Apply</div>
        <div className="p-3">Suggestion Type</div>
        <div className="p-3">Section</div>
        <div className="p-3">Before</div>
        <div className="p-3">After</div>
      </div>
      {rows.map((row, idx) => {
        const style = TYPE_STYLES[row.type]
        const checked = acceptedIndices.has(idx)
        return (
          <label
            key={idx}
            className={`grid grid-cols-[40px_140px_140px_1fr_1fr] border-b border-slate-200 last:border-b-0 text-sm cursor-pointer transition-colors ${
              checked ? 'bg-blue-50/50' : 'hover:bg-slate-50'
            }`}
          >
            <div className="p-3 flex items-center justify-center">
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onToggle(idx)}
                className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500"
                aria-label={`Approve ${row.type} for ${row.section}`}
              />
            </div>
            <div className={`p-3 ${style.header}`}>
              <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${style.pill}`}>
                {row.type}
              </span>
            </div>
            <div className="p-3 text-slate-700 font-medium">{row.section}</div>
            <div className="p-3 text-slate-700 whitespace-pre-wrap break-words bg-red-50/40">
              {row.before}
            </div>
            <div className="p-3 text-slate-700 whitespace-pre-wrap break-words bg-green-50/40">
              {row.after}
            </div>
          </label>
        )
      })}
    </div>
  )
}

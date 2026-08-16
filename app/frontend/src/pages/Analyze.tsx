import { useEffect, useMemo, useRef, useState } from 'react'
import {
  useResumes,
  useGoalSets,
  useRunAnalysis,
  useGetSuggestions,
  useApplySuggestions,
  usePendingImports,
  useConsumeImport,
  useDismissImport,
  type PendingImport,
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
  Link,
  Image,
  FileText,
  X,
  Pencil,
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

type JdQueueItem = {
  id: string
  title: string      // first non-empty line of the JD, used as display label
  text: string
  addedAt: string    // ISO timestamp
}

const JD_QUEUE_KEY = 'launchpad_jd_queue'

function loadQueue(): JdQueueItem[] {
  try {
    return JSON.parse(localStorage.getItem(JD_QUEUE_KEY) ?? '[]')
  } catch { return [] }
}

function saveQueue(q: JdQueueItem[]) {
  localStorage.setItem(JD_QUEUE_KEY, JSON.stringify(q))
}

// Defined outside the component so the interval closure always captures the
// same reference and the array is never recreated on re-render.
const LOADING_STEPS = [
  { p: 10,  msg: "Reading resume content…" },
  { p: 30,  msg: "Extracting JD requirements…" },
  { p: 60,  msg: "AI comparing dimensions…" },
  { p: 85,  msg: "Calculating final scores…" },
  { p: 98,  msg: "Almost there…" },
]

const SUGGESTIONS_STEPS = [
  { p: 15,  msg: "Reading your resume…" },
  { p: 40,  msg: "Mapping gaps to JD requirements…" },
  { p: 70,  msg: "Drafting targeted suggestions…" },
  { p: 92,  msg: "Finalising changes…" },
]

const GOAL_STEPS = [
  { p: 20,  msg: "Reading resume content…" },
  { p: 55,  msg: "Identifying career dimensions…" },
  { p: 85,  msg: "Building scoring metrics…" },
  { p: 97,  msg: "Almost ready…" },
]

/* ─── Shared modal overlay loader ───────────────────────────────────────────
   Renders as a fixed full-screen overlay with a frosted backdrop so the page
   content remains visible but dimmed behind it.
   ─────────────────────────────────────────────────────────────────────────── */
function LoadingModal({ step, progress }: { step: string; progress: number }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* semi-transparent backdrop — page content shows through */}
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" />
      {/* card */}
      <div className="relative z-10 bg-white rounded-2xl shadow-2xl px-10 py-8 w-full max-w-md mx-4">
        {/* animated icon */}
        <div className="flex justify-center mb-5">
          <div className="w-12 h-12 rounded-full border-4 border-blue-100 border-t-blue-600 animate-spin" />
        </div>
        <p className="text-center text-blue-600 font-semibold text-base mb-4">{step}</p>
        {/* progress bar */}
        <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden mb-2">
          <div
            className="bg-blue-600 h-full rounded-full transition-all duration-700 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="text-right text-xs text-slate-400">{progress}%</p>
        <p className="text-center text-slate-400 text-sm mt-3 animate-pulse">
          This usually takes 10–20 seconds…
        </p>
      </div>
    </div>
  )
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
  const [jdMode, setJdMode] = useState<'text' | 'url' | 'image'>('text')
  const [jdUrl, setJdUrl] = useState('')
  const [jdImage, setJdImage] = useState<{ base64: string; mediaType: string; preview: string } | null>(null)
  const [jdExtracting, setJdExtracting] = useState(false)
  const [jdExtractError, setJdExtractError] = useState<string | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [suggestions, setSuggestions] = useState<Suggestions | null>(null)
  const [userPrompt, setUserPrompt] = useState('')
  const [forceSuggestions, setForceSuggestions] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [progress, setProgress] = useState(0)
  const [loadingStep, setLoadingStep] = useState("")

  const [suggestProgress, setSuggestProgress] = useState(0)
  const [suggestStep, setSuggestStep] = useState("")

  const [jdQueue, setJdQueue] = useState<JdQueueItem[]>(loadQueue)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const { mutate: runAnalysis, isPending: analyzing } = useRunAnalysis()
  const { mutate: getSuggestions, isPending: suggesting } = useGetSuggestions()

  // ── Pending imports from the browser extension ─────────────────────────────
  // Polled every 10 s by usePendingImports(); the banner below the form lets
  // the user one-click any import — which auto-fills the JD textarea and
  // marks the import consumed on the server.
  const { data: pendingImports = [] } = usePendingImports()
  const { mutate: consumeImport } = useConsumeImport()
  const { mutate: dismissImport } = useDismissImport()

  const handleUseImport = (imp: PendingImport) => {
    setJdText(imp.jd_text)
    if (imp.url) setJdUrl(imp.url)
    setJdMode('text')
    consumeImport(imp.id)
    setTimeout(() => {
      textareaRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      textareaRef.current?.focus()
    }, 100)
  }

  // ── Chrome extension JD prefill ──────────────────────────────────────────
  // The extension navigates this tab to /#jd=<base64> when the user clicks
  // "Open in Launchpad". Two scenarios:
  //   A. Tab was closed → extension opens a new tab → component mounts with
  //      hash already in the URL → applyHash() fires on mount.
  //   B. Tab already open → extension does a hash navigation → no remount →
  //      'hashchange' event fires → applyHash() fires from the listener.
  useEffect(() => {
    function applyHash() {
      const m = window.location.hash.match(/[#&]jd=([A-Za-z0-9+/=]+)/)
      if (!m?.[1]) return
      // Clear hash immediately so refresh doesn't re-apply it
      window.history.replaceState(null, '', window.location.pathname + window.location.search)
      try {
        const text = decodeURIComponent(escape(atob(m[1])))
        if (text.length > 50) {
          setJdText(text)
          setJdMode('text')
          setCurrentTab('analyze')
          setTimeout(() => {
            document.querySelector('textarea')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
          }, 150)
        }
      } catch { /* malformed base64 — ignore */ }
    }

    applyHash()                                        // Scenario A — on mount
    window.addEventListener('hashchange', applyHash)  // Scenario B — already open
    return () => window.removeEventListener('hashchange', applyHash)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
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

  const handleAddToQueue = () => {
    if (!jdText.trim()) return
    const firstLine = jdText.split('\n').find(l => l.trim().length > 0) ?? 'Untitled JD'
    const item: JdQueueItem = {
      id: Date.now().toString(),
      title: firstLine.trim().slice(0, 80),
      text: jdText,
      addedAt: new Date().toISOString(),
    }
    const updated = [item, ...jdQueue]
    setJdQueue(updated)
    saveQueue(updated)
    // Clear the input after parking
    setJdText('')
    setJdMode('text')
  }

  const handleEditFromQueue = (item: JdQueueItem) => {
    setJdText(item.text)
    setJdMode('text')
    // Scroll JD box into view, then focus + move cursor to end
    setTimeout(() => {
      const el = textareaRef.current
      if (!el) return
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.focus()
      el.setSelectionRange(el.value.length, el.value.length)
    }, 120)
  }

  const handleAnalyseFromQueue = (item: JdQueueItem) => {
    setJdText(item.text)
    setJdMode('text')
    // Remove from queue immediately
    const updated = jdQueue.filter(i => i.id !== item.id)
    setJdQueue(updated)
    saveQueue(updated)
    // Kick off analysis after state settles
    setTimeout(() => {
      handleRunAnalysis(item.text)
    }, 50)
  }

  const handleRemoveFromQueue = (id: string) => {
    const updated = jdQueue.filter(i => i.id !== id)
    setJdQueue(updated)
    saveQueue(updated)
  }

  const handleRunAnalysis = (overrideText?: string) => {
    setError(null)
    const activeJd = typeof overrideText === 'string' ? overrideText : jdText
    if (!selectedResume || !selectedGoalSet || !activeJd.trim()) {
      setError('Pick a resume, a goal set, and provide a job description (paste text, extract from URL, or upload a screenshot).')
      return
    }

    // Seed the first step immediately so the loader is never blank.
    setProgress(LOADING_STEPS[0].p)
    setLoadingStep(LOADING_STEPS[0].msg)
    let currentStep = 1
    const interval = setInterval(() => {
      if (currentStep < LOADING_STEPS.length) {
        setLoadingStep(LOADING_STEPS[currentStep].msg)
        setProgress(LOADING_STEPS[currentStep].p)
        currentStep++
      } else {
        clearInterval(interval)
      }
    }, 2000)

    runAnalysis(
      { resumeName: selectedResume, goalSetId: selectedGoalSet, jdText: activeJd },
      {
        onSuccess: (data: any) => {
          clearInterval(interval)
          setProgress(0)
          setLoadingStep("")
          setResult(data as AnalysisResult)
          // /run now returns suggestions in the same response — apply them immediately
          if (data.suggestions) {
            setSuggestions(data.suggestions as Suggestions)
          } else {
            setSuggestions(null)
          }
          setForceSuggestions(false)
          // Remove from queue if this JD was loaded from there
          const updated = jdQueue.filter(i => i.text !== activeJd)
          if (updated.length !== jdQueue.length) {
            setJdQueue(updated)
            saveQueue(updated)
          }
        },
        onError: (e: any) => {
          clearInterval(interval)
          setProgress(0)
          setLoadingStep("")
          setError(e?.response?.data?.detail ?? e?.message ?? 'Analysis failed')
        },
      },
    )
  }

  const handleGetSuggestions = (override = false) => {
    if (!result) return

    setSuggestProgress(SUGGESTIONS_STEPS[0].p)
    setSuggestStep(SUGGESTIONS_STEPS[0].msg)
    let step = 1
    const interval = setInterval(() => {
      if (step < SUGGESTIONS_STEPS.length) {
        setSuggestStep(SUGGESTIONS_STEPS[step].msg)
        setSuggestProgress(SUGGESTIONS_STEPS[step].p)
        step++
      } else {
        clearInterval(interval)
      }
    }, 2000)

    getSuggestions(
      {
        resumeName: result.resume_name,
        jdJson: result.jd,
        gaps: result.scorecard.gaps,
        userPrompt: userPrompt.trim() || undefined,
        override,
      },
      {
        onSuccess: (data) => {
          clearInterval(interval)
          setSuggestProgress(0)
          setSuggestStep("")
          setSuggestions(data as Suggestions)
        },
        onError: () => {
          clearInterval(interval)
          setSuggestProgress(0)
          setSuggestStep("")
        },
      },
    )
  }

  const handleStartNew = () => {
    setResult(null)
    setSuggestions(null)
    setUserPrompt('')
    setJdText('')
    setJdUrl('')
    setJdImage(null)
    setJdMode('text')
    setJdExtractError(null)
    setForceSuggestions(false)
    setError(null)
    // jdQueue intentionally preserved — user may want to analyse the next one
  }

  const handleExtractFromUrl = async () => {
    if (!jdUrl.trim()) return
    setJdExtracting(true)
    setJdExtractError(null)
    try {
      const res = await fetch('/api/analyze/extract-jd-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: jdUrl.trim() }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Extraction failed')
      setJdText(data.jd_text)
      setJdMode('text')   // switch to text tab to show the extracted content
    } catch (e: any) {
      setJdExtractError(e.message ?? 'Could not extract JD from that URL')
    } finally {
      setJdExtracting(false)
    }
  }

  const handleImageFile = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = reader.result as string
      const [meta, base64] = dataUrl.split(',')
      const mediaType = meta.match(/:(.*?);/)?.[1] ?? 'image/png'
      setJdImage({ base64, mediaType, preview: dataUrl })
      setJdExtractError(null)
    }
    reader.readAsDataURL(file)
  }

  const handleExtractFromImage = async () => {
    if (!jdImage) return
    setJdExtracting(true)
    setJdExtractError(null)
    try {
      const res = await fetch('/api/analyze/extract-jd-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_base64: jdImage.base64, media_type: jdImage.mediaType }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Extraction failed')
      setJdText(data.jd_text)
      setJdMode('text')   // switch to show extracted text
    } catch (e: any) {
      setJdExtractError(e.message ?? 'Could not extract text from image')
    } finally {
      setJdExtracting(false)
    }
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
      {/* Analysis loader modal — renders over the form, keeping it visible */}
      {analyzing && <LoadingModal step={loadingStep} progress={progress} />}
      {/* Suggestions loader modal */}
      {suggesting && <LoadingModal step={suggestStep} progress={suggestProgress} />}

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
        <>
          {/* ── Pending extension imports banner ──────────────────────────── */}
          {pendingImports.length > 0 && (
            <Card className="border-blue-200 bg-blue-50/50">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h2 className="text-sm font-bold text-blue-900 uppercase tracking-wide">
                    {pendingImports.length} import{pendingImports.length === 1 ? '' : 's'} from browser extension
                  </h2>
                  <p className="text-xs text-blue-700 mt-0.5">
                    Click one to load it into the JD field below.
                  </p>
                </div>
              </div>
              <div className="space-y-2">
                {pendingImports.map((imp) => (
                  <div
                    key={imp.id}
                    className="bg-white border border-blue-200 rounded-lg p-3 flex items-center gap-3 hover:border-blue-400 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {imp.jd_title || imp.host || 'Untitled JD'}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5 truncate">
                        {imp.host ?? imp.url ?? 'unknown source'}
                        {' · '}
                        {imp.jd_text.length.toLocaleString()} chars
                        {' · '}
                        {new Date(imp.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                    <button
                      onClick={() => handleUseImport(imp)}
                      className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-700 text-white whitespace-nowrap"
                    >
                      Use this JD
                    </button>
                    <button
                      onClick={() => dismissImport(imp.id)}
                      aria-label="Dismiss"
                      className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          )}

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

            <JdInput
              mode={jdMode}
              onModeChange={(m) => { setJdMode(m); setJdExtractError(null) }}
              jdText={jdText}
              onJdTextChange={setJdText}
              jdUrl={jdUrl}
              onJdUrlChange={setJdUrl}
              jdImage={jdImage}
              onImageFile={handleImageFile}
              onClearImage={() => setJdImage(null)}
              onExtractFromUrl={handleExtractFromUrl}
              onExtractFromImage={handleExtractFromImage}
              extracting={jdExtracting}
              extractError={jdExtractError}
              textareaRef={textareaRef}
            />

            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
                {error}
              </div>
            )}

            <div className="flex gap-3">
              <Button
                variant="secondary"
                onClick={handleAddToQueue}
                disabled={!jdText.trim()}
                className="flex-none px-5"
                title="Park this JD to analyse later"
              >
                + Add
              </Button>
              <Button onClick={() => handleRunAnalysis()} loading={analyzing} className="flex-1">
                <Play className="w-4 h-4 inline mr-2" />
                Run Analysis
              </Button>
            </div>
          </div>
        </Card>

        {/* ── JD Queue ──────────────────────────────────────────────────── */}
        {jdQueue.length > 0 && (
          <Card>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">
                  Job Descriptions to Analyse
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  {jdQueue.length} parked — click "Analyse" to load one into the box above
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wide pb-2 pl-1 w-full">
                      Job Description
                    </th>
                    <th className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wide pb-2 px-4 whitespace-nowrap">
                      Added
                    </th>
                    <th className="pb-2 px-1 w-32"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {jdQueue.map((item) => (
                    <tr key={item.id} className="group hover:bg-slate-50 transition-colors">
                      <td className="py-3 pl-1 pr-4">
                        <p className="font-medium text-slate-800 truncate max-w-xs">{item.title}</p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {item.text.length.toLocaleString()} chars
                        </p>
                      </td>
                      <td className="py-3 px-4 text-slate-400 whitespace-nowrap text-xs">
                        {new Date(item.addedAt).toLocaleDateString(undefined, {
                          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                        })}
                      </td>
                      <td className="py-3 px-1">
                        <div className="flex items-center gap-2 justify-end">
                          <button
                            onClick={() => handleEditFromQueue(item)}
                            className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition-colors whitespace-nowrap flex items-center gap-1"
                            title="Load into JD box to review or edit"
                          >
                            <Pencil className="w-3 h-3" />
                            Edit
                          </button>
                          <button
                            onClick={() => handleAnalyseFromQueue(item)}
                            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg transition-colors whitespace-nowrap flex items-center gap-1"
                            title="Run analysis immediately"
                          >
                            <Play className="w-3 h-3" />
                            Analyse
                          </button>
                          <button
                            onClick={() => handleRemoveFromQueue(item.id)}
                            className="p-1.5 text-slate-300 hover:text-red-400 transition-colors rounded"
                            title="Remove from queue"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
        </>
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
   JD Input — Text / URL / Screenshot tabs
   ───────────────────────────────────────────── */

type JdMode = 'text' | 'url' | 'image'

function JdInput({
  mode, onModeChange,
  jdText, onJdTextChange,
  jdUrl, onJdUrlChange,
  jdImage, onImageFile, onClearImage,
  onExtractFromUrl, onExtractFromImage,
  extracting, extractError,
  textareaRef,
}: {
  mode: JdMode
  onModeChange: (m: JdMode) => void
  jdText: string
  onJdTextChange: (v: string) => void
  jdUrl: string
  onJdUrlChange: (v: string) => void
  jdImage: { base64: string; mediaType: string; preview: string } | null
  onImageFile: (f: File) => void
  onClearImage: () => void
  onExtractFromUrl: () => void
  onExtractFromImage: () => void
  extracting: boolean
  extractError: string | null
  textareaRef?: React.RefObject<HTMLTextAreaElement>
}) {
  const tabs: { key: JdMode; label: string; Icon: any }[] = [
    { key: 'text',  label: 'Paste Text',  Icon: FileText },
    { key: 'url',   label: 'From URL',    Icon: Link },
    { key: 'image', label: 'Screenshot',  Icon: Image },
  ]

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file && file.type.startsWith('image/')) onImageFile(file)
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    const item = Array.from(e.clipboardData.items).find(i => i.type.startsWith('image/'))
    if (item) {
      e.preventDefault()
      const file = item.getAsFile()
      if (file) onImageFile(file)
    }
  }

  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-2">Job Description</label>

      {/* Tab bar */}
      <div className="flex gap-1 mb-3 bg-slate-100 p-1 rounded-lg w-fit">
        {tabs.map(({ key, label, Icon }) => (
          <button
            key={key}
            type="button"
            onClick={() => onModeChange(key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              mode === key
                ? 'bg-white text-blue-600 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* ── Tab: Paste Text ── */}
      {mode === 'text' && (
        <textarea
          ref={textareaRef}
          value={jdText}
          onChange={(e) => onJdTextChange(e.target.value)}
          placeholder="Paste the full job description here…"
          rows={10}
          className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
        />
      )}

      {/* ── Tab: From URL ── */}
      {mode === 'url' && (
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="url"
              value={jdUrl}
              onChange={(e) => onJdUrlChange(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onExtractFromUrl()}
              placeholder="https://www.linkedin.com/jobs/view/… or any job posting URL"
              className="flex-1 px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
            <Button
              onClick={onExtractFromUrl}
              loading={extracting}
              disabled={!jdUrl.trim() || extracting}
            >
              {extracting ? 'Extracting…' : 'Extract JD'}
            </Button>
          </div>
          <p className="text-xs text-slate-400">
            Works with LinkedIn, Greenhouse, Lever, Workday, company career pages and most public job boards.
            Some sites block scraping — paste the text directly if extraction fails.
          </p>
          {extractError && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {extractError}
            </p>
          )}
          {/* Preview extracted text if already done */}
          {!extracting && !extractError && jdText && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2 text-sm text-green-800 flex items-start gap-2">
              <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-green-600" />
              <span>JD extracted ({jdText.length.toLocaleString()} characters). Switch to "Paste Text" tab to review or edit.</span>
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Screenshot ── */}
      {mode === 'image' && (
        <div className="space-y-3">
          {!jdImage ? (
            <label
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              onPaste={handlePaste}
              className="border-2 border-dashed border-slate-300 hover:border-blue-400 rounded-lg p-8 text-center cursor-pointer transition-colors focus-within:border-blue-500 outline-none block"
              tabIndex={0}
            >
              <Image className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <p className="text-slate-600 font-medium text-sm">Drop, paste (Ctrl+V), or click to upload a screenshot</p>
              <p className="text-xs text-slate-400 mt-1">PNG, JPEG, WEBP supported</p>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="sr-only"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) onImageFile(f) }}
              />
            </label>
          ) : (
            <div className="space-y-3">
              <div className="relative w-full rounded-lg overflow-hidden border border-slate-200 bg-slate-50">
                <img
                  src={jdImage.preview}
                  alt="JD screenshot"
                  className="w-full max-h-72 object-contain"
                />
                <button
                  onClick={onClearImage}
                  className="absolute top-2 right-2 bg-white/90 hover:bg-white rounded-full p-1 shadow border border-slate-200"
                  aria-label="Remove image"
                >
                  <X className="w-4 h-4 text-slate-600" />
                </button>
              </div>
              <Button
                onClick={onExtractFromImage}
                loading={extracting}
                disabled={extracting}
                className="w-full"
              >
                <Sparkles className="w-4 h-4 inline mr-2" />
                {extracting ? 'Extracting text from screenshot…' : 'Extract JD from Screenshot'}
              </Button>
            </div>
          )}
          {extractError && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {extractError}
            </p>
          )}
          {!extracting && !extractError && jdText && jdImage && (
            <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2 text-sm text-green-800 flex items-start gap-2">
              <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-green-600" />
              <span>Text extracted ({jdText.length.toLocaleString()} characters). Switch to "Paste Text" tab to review or edit.</span>
            </div>
          )}
        </div>
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
      <Card className="overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100">
          <h3 className="text-base font-semibold text-slate-900">Scorecard</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            {scorecard.scores.length} dimension{scorecard.scores.length !== 1 ? 's' : ''} scored
          </p>
        </div>
        <table className="w-full text-left">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-6 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide w-44">
                Metric
              </th>
              <th className="px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide w-40">
                Score
              </th>
              <th className="px-6 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Analysis
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {scorecard.scores.map((row, i) => {
              const pct = (row.score / 10) * 100
              const barColor = row.score >= 7.5 ? 'bg-green-500'
                             : row.score >= 5.5 ? 'bg-amber-500'
                             : 'bg-red-500'
              const scoreColor = row.score >= 7.5 ? 'text-green-700 bg-green-50 border-green-200'
                               : row.score >= 5.5 ? 'text-amber-700 bg-amber-50 border-amber-200'
                               : 'text-red-700 bg-red-50 border-red-200'
              return (
                <tr key={i} className="hover:bg-slate-50/60 transition-colors">
                  {/* Metric name */}
                  <td className="px-6 py-4">
                    <span className="text-sm font-semibold text-slate-800 leading-snug">
                      {row.dimension}
                    </span>
                  </td>
                  {/* Score: badge + progress bar */}
                  <td className="px-4 py-4">
                    <div className="flex flex-col gap-1.5">
                      <span className={`inline-block px-2 py-0.5 rounded-md text-xs font-bold border ${scoreColor} w-fit`}>
                        {row.score.toFixed(1)}<span className="font-normal opacity-60">/10</span>
                      </span>
                      <div className="w-32 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${barColor}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  {/* Remark */}
                  <td className="px-6 py-4 text-sm text-slate-600 leading-relaxed">
                    {row.remark}
                  </td>
                </tr>
              )
            })}
          </tbody>
          {/* Overall fit footer row */}
          <tfoot className="bg-slate-50 border-t-2 border-slate-200">
            <tr>
              <td className="px-6 py-3 text-sm font-bold text-slate-700">Overall Fit</td>
              <td className="px-4 py-3">
                <span className={`inline-block px-2.5 py-1 rounded-md text-sm font-bold border ${
                  scorecard.overall_fit >= 7.5 ? 'text-green-700 bg-green-50 border-green-200'
                  : scorecard.overall_fit >= 5.5 ? 'text-amber-700 bg-amber-50 border-amber-200'
                  : 'text-red-700 bg-red-50 border-red-200'
                }`}>
                  {scorecard.overall_fit.toFixed(1)}<span className="font-normal opacity-60">/10</span>
                </span>
              </td>
              <td className="px-6 py-3 text-sm text-slate-500 italic">
                Weighted mean across all dimensions
              </td>
            </tr>
          </tfoot>
        </table>
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

export { LoadingModal, GOAL_STEPS }
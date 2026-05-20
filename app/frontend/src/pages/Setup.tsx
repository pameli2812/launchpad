import {
  useResumes,
  useUploadResume,
  useDeleteResume,
  useGoalSets,
  useCreateGoalSet,
  useDeleteGoalSet,
  useActivateGoalSet,
  useDeactivateGoalSet,
  useAutoInferGoals,
} from '@/hooks'
import { setupAPI } from '@/api/client'
import { Button, Card, Input } from '@/components/UI'
import {
  Upload,
  Plus,
  Eye,
  Trash2,
  X,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Pencil,
} from 'lucide-react'
import { useMemo, useState } from 'react'

type Metric = {
  id: string
  label: string
  description: string
  autoInferred: boolean
}

type Resume = {
  name: string
  size: number
  modified: string
}

type GoalSet = {
  id: string
  name: string
  goals: any[]
  created_at?: string
  is_active?: boolean
}

const RESUMES_PAGE_SIZE = 5

function shortId() {
  return Math.random().toString(36).slice(2, 10)
}

export function SetupPage() {
  const [showCreateGoal, setShowCreateGoal] = useState(false)
  const [expandedGoalId, setExpandedGoalId] = useState<string | null>(null)
  const [resumePage, setResumePage] = useState(0)

  const { data: resumes = [], isLoading: resumesLoading } = useResumes()
  const { mutate: uploadResume, isPending: uploading } = useUploadResume()
  const { mutate: deleteResume } = useDeleteResume()
  const { data: goalSets = [] } = useGoalSets()
  const { mutate: activateGoalSet } = useActivateGoalSet()
  const { mutate: deactivateGoalSet } = useDeactivateGoalSet()
  const { mutate: deleteGoalSet } = useDeleteGoalSet()

  const totalPages = Math.max(1, Math.ceil(resumes.length / RESUMES_PAGE_SIZE))
  const pagedResumes = useMemo(
    () => resumes.slice(resumePage * RESUMES_PAGE_SIZE, (resumePage + 1) * RESUMES_PAGE_SIZE),
    [resumes, resumePage],
  )

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      uploadResume(file)
      e.target.value = ''
    }
  }

  const handleView = (name: string) => {
    window.open(setupAPI.getResumeViewUrl(name), '_blank', 'noopener,noreferrer')
  }

  const handleDelete = (name: string) => {
    if (window.confirm(`Delete "${name}"? This cannot be undone.`)) {
      deleteResume(name)
    }
  }

  const handleToggleActive = (gs: GoalSet) => {
    if (gs.is_active) {
      deactivateGoalSet(gs.id)
    } else {
      activateGoalSet(gs.id)
    }
  }

  const handleDeleteGoalSet = (gs: GoalSet) => {
    if (window.confirm(`Delete goal set "${gs.name}"?`)) {
      deleteGoalSet(gs.id)
    }
  }

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-12">
      {/* ════════════ Step 1: Resumes ════════════ */}
      <section>
        <div className="flex justify-between items-end border-b border-slate-200 pb-6 mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Step 1: Resumes</h2>
            <p className="text-slate-500 text-sm mt-1">Upload and manage your resumes</p>
          </div>
        </div>

        <div className="mb-6">
          <label htmlFor="file-upload" className="block cursor-pointer">
            <Card className="border-2 border-dashed border-slate-300 hover:border-blue-400 transition-colors p-8">
              <div className="text-center">
                <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                <p className="text-slate-600 font-medium">
                  {uploading ? 'Uploading…' : 'Click to upload resume (PDF or DOCX)'}
                </p>
                <input
                  id="file-upload"
                  type="file"
                  accept=".pdf,.docx"
                  onChange={handleFileUpload}
                  className="hidden"
                  disabled={uploading}
                />
              </div>
            </Card>
          </label>
        </div>

        {resumesLoading ? (
          <p className="text-slate-500">Loading resumes…</p>
        ) : (
          <>
            <div className="border border-slate-200 rounded-lg overflow-hidden">
              <div className="grid grid-cols-[3fr_1fr_1.5fr_auto_auto] bg-slate-100 border-b border-slate-200">
                <div className="p-4 font-semibold text-slate-900">File Name</div>
                <div className="p-4 font-semibold text-slate-900 text-center">Size</div>
                <div className="p-4 font-semibold text-slate-900 text-center">Last Modified</div>
                <div className="p-4 font-semibold text-slate-900 text-center">View</div>
                <div className="p-4 font-semibold text-slate-900 text-center">Delete</div>
              </div>
              {resumes.length === 0 ? (
                <div className="p-8 text-center text-slate-500">No resumes uploaded yet</div>
              ) : (
                pagedResumes.map((resume: Resume) => (
                  <div
                    key={resume.name}
                    className="grid grid-cols-[3fr_1fr_1.5fr_auto_auto] border-b border-slate-200 last:border-b-0 hover:bg-slate-50 items-center"
                  >
                    <div className="p-4 text-slate-900 break-all" title={resume.name}>
                      {resume.name}
                    </div>
                    <div className="p-4 text-slate-600 text-center">
                      {Math.round(resume.size / 1024)} KB
                    </div>
                    <div className="p-4 text-slate-600 text-center text-sm">{resume.modified}</div>
                    <div className="p-4 text-center">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleView(resume.name)}
                        aria-label={`View ${resume.name}`}
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                    </div>
                    <div className="p-4 text-center">
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleDelete(resume.name)}
                        aria-label={`Delete ${resume.name}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {resumes.length > RESUMES_PAGE_SIZE && (
              <div className="flex items-center justify-between mt-3 text-sm">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setResumePage((p) => Math.max(0, p - 1))}
                  disabled={resumePage === 0}
                >
                  Previous
                </Button>
                <span className="text-slate-500">
                  Page {resumePage + 1} of {totalPages} · {resumes.length} resumes
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setResumePage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={resumePage >= totalPages - 1}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </section>

      {/* ════════════ Step 2: Goals ════════════ */}
      <section>
        <div className="flex justify-between items-end border-b border-slate-200 pb-6 mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Step 2: Goals</h2>
            <p className="text-slate-500 text-sm mt-1">
              Existing goal sets — pick one to use for analysis or create a new one
            </p>
          </div>
        </div>

        {/* Existing goal sets table */}
        {goalSets.length === 0 ? (
          <p className="text-slate-500 mb-6">No goal sets yet — click “Add New Goal” to create one.</p>
        ) : (
          <div className="border border-slate-200 rounded-lg overflow-hidden mb-6">
            <div className="grid grid-cols-[2.5fr_0.8fr_2.5fr_1fr_auto_auto_auto] bg-slate-100 border-b border-slate-200">
              <div className="p-4 font-semibold text-slate-900">Goal Name</div>
              <div className="p-4 font-semibold text-slate-900 text-center">Metrics</div>
              <div className="p-4 font-semibold text-slate-900">Description</div>
              <div className="p-4 font-semibold text-slate-900 text-center">Status</div>
              <div className="p-4 font-semibold text-slate-900 text-center">View</div>
              <div className="p-4 font-semibold text-slate-900 text-center">Delete</div>
              <div className="p-4 font-semibold text-slate-900 text-center">Action</div>
            </div>
            {goalSets.map((gs: GoalSet) => {
              const firstDesc = gs.goals?.[0]?.description ?? ''
              const descPreview =
                firstDesc.length > 60 ? firstDesc.slice(0, 60) + '…' : firstDesc || '—'
              const expanded = expandedGoalId === gs.id
              return (
                <div key={gs.id} className="border-b border-slate-200 last:border-b-0">
                  <div className="grid grid-cols-[2.5fr_0.8fr_2.5fr_1fr_auto_auto_auto] hover:bg-slate-50 items-center">
                    <div className="p-4 font-medium text-slate-900">{gs.name}</div>
                    <div className="p-4 text-slate-600 text-center">{gs.goals?.length ?? 0}</div>
                    <div className="p-4 text-slate-600 text-sm">{descPreview}</div>
                    <div className="p-4 text-center">
                      <span
                        className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                          gs.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {gs.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <div className="p-4 text-center">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setExpandedGoalId(expanded ? null : gs.id)}
                        aria-label={expanded ? 'Collapse' : 'Expand'}
                      >
                        {expanded ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                    <div className="p-4 text-center">
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleDeleteGoalSet(gs)}
                        aria-label={`Delete ${gs.name}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                    <div className="p-4 text-center">
                      <button
                        onClick={() => handleToggleActive(gs)}
                        className={`text-xs font-semibold rounded-md px-3 py-1.5 transition-colors ${
                          gs.is_active
                            ? 'bg-green-600 text-white hover:bg-green-700'
                            : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                        }`}
                      >
                        {gs.is_active ? '✓ Active' : 'Activate'}
                      </button>
                    </div>
                  </div>

                  {expanded && (
                    <div className="px-6 py-4 bg-slate-50 border-t border-slate-200">
                      <p className="text-sm font-semibold text-slate-700 mb-2">Metrics in this set:</p>
                      <ul className="space-y-2">
                        {gs.goals?.map((g: any) => (
                          <li key={g.id} className="text-sm">
                            <span className="font-medium text-slate-900">{g.label}</span>
                            {g.description && (
                              <span className="text-slate-500"> — {g.description}</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {!showCreateGoal ? (
          <Button onClick={() => setShowCreateGoal(true)} disabled={resumes.length === 0}>
            <Plus className="w-4 h-4 inline mr-2" />
            Add New Goal
          </Button>
        ) : (
          <CreateGoalPanel
            resumes={resumes}
            onClose={() => setShowCreateGoal(false)}
            onSaved={() => setShowCreateGoal(false)}
          />
        )}
        {resumes.length === 0 && !showCreateGoal && (
          <p className="text-sm text-slate-500 mt-2">Upload a resume first to create goal sets.</p>
        )}
      </section>
    </div>
  )
}

/* ─────────────────────────────────────────────
   Create Goal Panel
   ───────────────────────────────────────────── */

function CreateGoalPanel({
  resumes,
  onClose,
  onSaved,
}: {
  resumes: Resume[]
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState('')
  const [mode, setMode] = useState<'auto' | 'manual'>('auto')
  const [selectedResume, setSelectedResume] = useState(resumes[0]?.name ?? '')
  const [context, setContext] = useState('')
  const [metrics, setMetrics] = useState<Metric[]>([])

  const { mutate: inferGoals, isPending: inferring } = useAutoInferGoals()
  const { mutate: createGoalSet, isPending: saving } = useCreateGoalSet()

  const handleGenerate = () => {
    if (!selectedResume) return
    inferGoals(
      { resumeName: selectedResume, context: context.trim() || undefined },
      {
        onSuccess: (goals: any[]) => {
          setMetrics(
            (goals ?? []).map((g) => ({
              id: shortId(),
              label: g.label ?? '',
              description: g.description ?? '',
              autoInferred: true,
            })),
          )
        },
      },
    )
  }

  const handleAddMetric = () => {
    setMetrics((m) => [...m, { id: shortId(), label: '', description: '', autoInferred: false }])
  }

  const handleUpdateMetric = (id: string, patch: Partial<Metric>) => {
    setMetrics((m) => m.map((x) => (x.id === id ? { ...x, ...patch } : x)))
  }

  const handleRemoveMetric = (id: string) => {
    setMetrics((m) => m.filter((x) => x.id !== id))
  }

  // When user switches to manual mode and there are no metrics yet, seed one empty row
  const switchMode = (next: 'auto' | 'manual') => {
    setMode(next)
    if (next === 'manual' && metrics.length === 0) {
      setMetrics([{ id: shortId(), label: '', description: '', autoInferred: false }])
    }
  }

  const validMetrics = metrics.filter((m) => m.label.trim())
  const canSave = name.trim().length > 0 && validMetrics.length > 0 && !saving

  const handleSave = () => {
    if (!canSave) return
    createGoalSet(
      {
        id: shortId(),
        name: name.trim(),
        goals: validMetrics.map((m) => ({
          id: `goal_${m.id}`,
          label: m.label.trim(),
          description: m.description.trim(),
          confidence: 'high',
          auto_inferred: m.autoInferred,
        })),
      },
      {
        onSuccess: () => onSaved(),
      },
    )
  }

  return (
    <Card className="border-blue-300 bg-blue-50">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-lg font-semibold text-slate-900">Create New Goal Set</h3>
        <button
          onClick={onClose}
          aria-label="Close"
          className="text-slate-500 hover:text-slate-900 p-1 rounded-full hover:bg-slate-200"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="space-y-5">
        <Input
          label="Goal Name"
          placeholder="e.g. Director of Product at AI Startup"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">How to create</label>
          <div className="flex gap-3">
            <ModeRadio
              label="Auto-Infer (AI)"
              icon={<Sparkles className="w-4 h-4" />}
              checked={mode === 'auto'}
              onClick={() => switchMode('auto')}
            />
            <ModeRadio
              label="Manual"
              icon={<Pencil className="w-4 h-4" />}
              checked={mode === 'manual'}
              onClick={() => switchMode('manual')}
            />
          </div>
        </div>

        {mode === 'auto' && (
          <div className="bg-white border border-slate-200 rounded-lg p-4 space-y-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Resume to infer from
              </label>
              <select
                value={selectedResume}
                onChange={(e) => setSelectedResume(e.target.value)}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                {resumes.length === 0 && <option value="">No resumes uploaded</option>}
                {resumes.map((r) => (
                  <option key={r.name} value={r.name}>
                    {r.name}
                  </option>
                ))}
              </select>
              <p className="text-xs text-slate-500 mt-1">
                Defaults to your most recent resume — change it here if you want goals inferred from
                a different one.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Additional context <span className="text-slate-400">(optional)</span>
              </label>
              <textarea
                value={context}
                onChange={(e) => setContext(e.target.value)}
                placeholder="e.g. I want GenAI/LLM roles, prefer remote, leadership-focused…"
                rows={3}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <Button onClick={handleGenerate} loading={inferring} disabled={!selectedResume}>
              <Sparkles className="w-4 h-4 inline mr-2" />
              Generate goals
            </Button>
          </div>
        )}

        {/* Metrics editor — shared between modes */}
        {(mode === 'manual' || metrics.length > 0) && (
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Metrics
              {mode === 'auto' && metrics.length > 0 && (
                <span className="text-slate-400 font-normal ml-2">
                  — review, edit, or add more before saving
                </span>
              )}
            </label>
            <div className="space-y-2">
              {metrics.map((m, idx) => (
                <div
                  key={m.id}
                  className="bg-white border border-slate-200 rounded-lg p-3 flex gap-3 items-start"
                >
                  <span className="text-slate-400 text-sm mt-2 w-6 text-right">{idx + 1}.</span>
                  <div className="flex-1 space-y-2">
                    <input
                      value={m.label}
                      onChange={(e) => handleUpdateMetric(m.id, { label: e.target.value })}
                      placeholder="Metric name (e.g. Senior PM at an AI-first company)"
                      className="w-full px-3 py-1.5 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                    />
                    <input
                      value={m.description}
                      onChange={(e) => handleUpdateMetric(m.id, { description: e.target.value })}
                      placeholder="Description (what does success look like?)"
                      className="w-full px-3 py-1.5 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                    />
                  </div>
                  <button
                    onClick={() => handleRemoveMetric(m.id)}
                    className="text-slate-400 hover:text-red-600 p-1"
                    aria-label="Remove metric"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
            <button
              onClick={handleAddMetric}
              className="mt-2 text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              + Add metric
            </button>
          </div>
        )}

        <div className="flex gap-2 pt-2 border-t border-slate-200">
          <Button onClick={handleSave} loading={saving} disabled={!canSave}>
            Save Goal Set
          </Button>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          {!canSave && !saving && (
            <span className="text-xs text-slate-500 self-center ml-2">
              {!name.trim()
                ? 'Enter a goal set name'
                : validMetrics.length === 0
                  ? 'Add at least one metric with a name'
                  : ''}
            </span>
          )}
        </div>
      </div>
    </Card>
  )
}

function ModeRadio({
  label,
  icon,
  checked,
  onClick,
}: {
  label: string
  icon: React.ReactNode
  checked: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg border font-medium text-sm transition-all ${
        checked
          ? 'border-blue-500 bg-blue-100 text-blue-700'
          : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
      }`}
    >
      <span
        className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
          checked ? 'border-blue-600' : 'border-slate-400'
        }`}
      >
        {checked && <span className="w-2 h-2 rounded-full bg-blue-600" />}
      </span>
      {icon}
      {label}
    </button>
  )
}

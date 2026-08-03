import { useEffect, useState } from 'react'
import {
  useResumes,
  useCompanySuggestion,
  useGenerateCompanySuggestion,
  type CompanyCard,
} from '@/hooks'
import { useAppStore } from '@/store'
import { Card } from '@/components/UI'
import {
  Building2, Sparkles, RefreshCw, ExternalLink, MapPin, Users,
  AlertCircle, FileText, Wifi,
} from 'lucide-react'

const SIZE_LABEL: Record<string, string> = {
  startup:    'Startup (<50)',
  small:      'Small (50–250)',
  mid:        'Mid (250–1k)',
  large:      'Large (1k–10k)',
  enterprise: 'Enterprise (10k+)',
}

const LIKELIHOOD_STYLES: Record<string, string> = {
  high:   'bg-green-100 text-green-700',
  medium: 'bg-amber-100 text-amber-700',
  low:    'bg-slate-100 text-slate-600',
}

export function CompanySuggestionPage() {
  const { data: resumes = [], isLoading: resumesLoading } = useResumes()
  const setCurrentTab = useAppStore((s) => s.setCurrentTab)

  const [selectedResume, setSelectedResume] = useState<string>('')
  const [userPrompt, setUserPrompt] = useState('')

  useEffect(() => {
    if (!selectedResume && resumes.length > 0) {
      setSelectedResume(resumes[0].name)
    }
  }, [resumes, selectedResume])

  const { data: suggestion, isLoading: suggestionLoading, error: suggestionError } =
    useCompanySuggestion(selectedResume)
  const { mutate: generate, isPending: generating, error: generateError } =
    useGenerateCompanySuggestion()

  // Sync the user_prompt field with what was last used for this resume,
  // so re-running with a tweak starts from the previous prompt.
  useEffect(() => {
    if (suggestion?.user_prompt && !userPrompt) {
      setUserPrompt(suggestion.user_prompt)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestion?.id])

  const handleGenerate = () => {
    if (!selectedResume) return
    generate({ resumeName: selectedResume, userPrompt: userPrompt.trim() || undefined })
  }

  // ── Empty states ──────────────────────────────────────────────────────────
  if (resumesLoading) {
    return <div className="max-w-6xl mx-auto p-8 text-slate-500">Loading…</div>
  }
  if (resumes.length === 0) {
    return (
      <div className="max-w-6xl mx-auto p-8">
        <Header />
        <Card className="text-center py-16">
          <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-700 font-semibold text-lg">No resumes yet</p>
          <p className="text-slate-400 text-sm mt-2 mb-5">
            Upload a resume in Setup, then come back here to see target companies.
          </p>
          <button
            onClick={() => setCurrentTab('setup')}
            className="px-4 py-2 rounded-lg font-medium bg-blue-600 hover:bg-blue-700 text-white"
          >
            Go to Setup
          </button>
        </Card>
      </div>
    )
  }

  const isAxios404 =
    (suggestionError as { response?: { status?: number } } | null)?.response?.status === 404
  const noSuggestionYet = !suggestion && !suggestionLoading && isAxios404

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-6">
      <Header />

      {/* Generator */}
      <Card>
        <div className="grid md:grid-cols-[1fr_auto] gap-3 items-end">
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Resume</label>
              <select
                value={selectedResume}
                onChange={(e) => setSelectedResume(e.target.value)}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                {resumes.map((r: { name: string }) => (
                  <option key={r.name} value={r.name}>{r.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Preferences <span className="text-slate-400 font-normal">(optional)</span>
              </label>
              <textarea
                value={userPrompt}
                onChange={(e) => setUserPrompt(e.target.value)}
                rows={2}
                placeholder="e.g. remote-only, Series A startups, EU companies, AI infra"
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <button
            onClick={handleGenerate}
            disabled={!selectedResume || generating}
            className="px-4 py-2 rounded-lg font-medium bg-blue-600 hover:bg-blue-700 text-white inline-flex items-center gap-2 disabled:opacity-50"
          >
            {generating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {generating ? 'Generating…' : suggestion ? 'Regenerate' : 'Generate companies'}
          </button>
        </div>
        {generateError && (
          <div className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
            {(generateError as { response?: { data?: { detail?: string } } } | undefined)
              ?.response?.data?.detail
              ?? (generateError as Error).message}
          </div>
        )}
      </Card>

      {/* States */}
      {suggestionLoading && (
        <Card className="text-center py-10 text-slate-500 text-sm">Loading suggestions…</Card>
      )}

      {noSuggestionYet && !generating && (
        <Card className="text-center py-14">
          <Building2 className="w-10 h-10 text-blue-300 mx-auto mb-3" />
          <p className="text-slate-700 font-semibold">No suggestions yet for this resume</p>
          <p className="text-slate-500 text-sm mt-1.5 max-w-md mx-auto">
            Add any preferences above (size, geography, focus) and click
            <strong> Generate companies</strong>. The LLM picks 10–15 specific companies
            and explains why each one fits.
          </p>
        </Card>
      )}

      {!noSuggestionYet && suggestionError && !generating && (
        <Card className="border-red-200 bg-red-50">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
            <div>
              <p className="font-semibold text-red-900">Could not load suggestions</p>
              <p className="text-sm text-red-700 mt-1">
                {(suggestionError as Error).message}
              </p>
            </div>
          </div>
        </Card>
      )}

      {suggestion?.companies?.length ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">
              {suggestion.companies.length} compan
              {suggestion.companies.length === 1 ? 'y' : 'ies'} suggested
              {suggestion.user_prompt && (
                <span className="ml-2 text-slate-400">
                  · using preferences: <em>{suggestion.user_prompt}</em>
                </span>
              )}
            </p>
            <p className="text-xs text-slate-400">
              Updated {new Date(suggestion.updated_at).toLocaleString()}
            </p>
          </div>
          {suggestion.companies.map((c, i) => (
            <CompanyRow key={`${c.name}-${i}`} c={c} />
          ))}
        </div>
      ) : suggestion ? (
        <Card className="text-center py-10 text-slate-500 text-sm">
          The LLM returned no companies. Try regenerating with broader preferences.
        </Card>
      ) : null}
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Header() {
  return (
    <div className="border-b border-slate-200 pb-6">
      <h1 className="text-3xl font-bold text-slate-900">Company Suggestion</h1>
      <p className="text-slate-500 mt-1 text-sm">
        Real companies likely to be a strong match for your resume — with the rationale
        tied to specific resume evidence.
      </p>
    </div>
  )
}

function CompanyRow({ c }: { c: CompanyCard }) {
  const likelihoodClass =
    LIKELIHOOD_STYLES[c.hiring_likelihood] ?? LIKELIHOOD_STYLES.medium

  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3 flex-wrap">
            <h3 className="text-lg font-semibold text-slate-900">
              {c.website ? (
                <a
                  href={c.website.startsWith('http') ? c.website : `https://${c.website}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-blue-600 inline-flex items-center gap-1.5"
                >
                  {c.name}
                  <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                </a>
              ) : c.name}
            </h3>
            {c.industry && (
              <span className="text-xs text-slate-500">{c.industry}</span>
            )}
            <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${likelihoodClass}`}>
              {c.hiring_likelihood} likelihood
            </span>
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-slate-500">
            {c.size && (
              <span className="inline-flex items-center gap-1">
                <Users className="w-3.5 h-3.5 text-slate-400" />
                {SIZE_LABEL[c.size] ?? c.size}
              </span>
            )}
            {c.location && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                {c.location}
              </span>
            )}
            {c.remote_policy && (
              <span className="inline-flex items-center gap-1 capitalize">
                <Wifi className="w-3.5 h-3.5 text-slate-400" />
                {c.remote_policy}
              </span>
            )}
          </div>

          {c.description && (
            <p className="text-sm text-slate-700 mt-3">{c.description}</p>
          )}

          {c.why_fit && (
            <div className="mt-3 bg-blue-50 border border-blue-100 rounded-lg p-3">
              <p className="text-xs font-semibold text-blue-900 mb-1">Why it fits you</p>
              <p className="text-sm text-blue-900">{c.why_fit}</p>
            </div>
          )}

          {c.focus_areas?.length ? (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {c.focus_areas.map((f, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs"
                >
                  {f}
                </span>
              ))}
            </div>
          ) : null}
        </div>

        <div className="flex-shrink-0 text-right">
          <div className="text-2xl font-bold text-blue-600 leading-none">
            {c.match_score.toFixed(1)}
          </div>
          <div className="text-xs text-slate-400 mt-1">match</div>
        </div>
      </div>
    </Card>
  )
}

import { useEffect, useState } from 'react'
import {
  useResumes,
  useResumeReview,
  useExtractResumeReview,
  type ResumeReview,
} from '@/hooks'
import { useAppStore } from '@/store'
import { Card } from '@/components/UI'
import {
  Sparkles, RefreshCw, Mail, Phone, MapPin, Linkedin,
  Briefcase, GraduationCap, Award, FolderGit2, AlertCircle, FileText,
} from 'lucide-react'

// ── Page ──────────────────────────────────────────────────────────────────────

export function ResumeReviewPage() {
  const { data: resumes = [], isLoading: resumesLoading } = useResumes()
  const setCurrentTab = useAppStore((s) => s.setCurrentTab)

  const [selectedResume, setSelectedResume] = useState<string>('')

  useEffect(() => {
    if (!selectedResume && resumes.length > 0) {
      setSelectedResume(resumes[0].name)
    }
  }, [resumes, selectedResume])

  const {
    data:   review,
    isLoading: reviewLoading,
    error:  reviewError,
  } = useResumeReview(selectedResume)

  const { mutate: extract, isPending: extracting, error: extractError } =
    useExtractResumeReview()

  const handleExtract = () => {
    if (!selectedResume) return
    extract(selectedResume)
  }

  // Show empty state if there are no resumes
  if (resumesLoading) {
    return <div className="max-w-6xl mx-auto p-8 text-slate-500">Loading…</div>
  }
  if (resumes.length === 0) {
    return (
      <div className="max-w-6xl mx-auto p-8">
        <div className="border-b border-slate-200 pb-6 mb-8">
          <h1 className="text-3xl font-bold text-slate-900">Resume Review</h1>
        </div>
        <Card className="text-center py-16">
          <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-700 font-semibold text-lg">No resumes yet</p>
          <p className="text-slate-400 text-sm mt-2 mb-5">
            Upload a resume in Setup, then come back here to extract a structured profile.
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

  // 404 from the GET = "no review yet" — that's a normal state, not an error
  const isAxiosNotFound =
    (reviewError as { response?: { status?: number } } | null)?.response?.status === 404
  const noReviewYet = !review && !reviewLoading && isAxiosNotFound

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-6">
      <div className="border-b border-slate-200 pb-6">
        <h1 className="text-3xl font-bold text-slate-900">Resume Review</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Structured profile extracted from your resume — contact, summary, skills, work
          history, education, certifications and projects.
        </p>
      </div>

      {/* Resume selector + extract button */}
      <Card>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
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
          <button
            onClick={handleExtract}
            disabled={!selectedResume || extracting}
            className="px-4 py-2 rounded-lg font-medium bg-blue-600 hover:bg-blue-700 text-white inline-flex items-center gap-2 disabled:opacity-50"
          >
            {extracting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {extracting ? 'Extracting…' : review ? 'Re-run review' : 'Run review'}
          </button>
        </div>
        {extractError && (
          <div className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
            {(extractError as { response?: { data?: { detail?: string } } } | undefined)?.response?.data?.detail
              ?? (extractError as Error).message}
          </div>
        )}
      </Card>

      {/* States */}
      {reviewLoading && (
        <Card className="text-center py-10 text-slate-500 text-sm">Loading review…</Card>
      )}

      {noReviewYet && !extracting && (
        <Card className="text-center py-14">
          <Sparkles className="w-10 h-10 text-blue-300 mx-auto mb-3" />
          <p className="text-slate-700 font-semibold">No review yet for this resume</p>
          <p className="text-slate-500 text-sm mt-1.5 max-w-md mx-auto">
            Click <strong>Run review</strong> above. The LLM reads the resume and pulls out
            your contact details, work history, skills and the rest into structured fields.
          </p>
        </Card>
      )}

      {!noReviewYet && reviewError && !extracting && (
        <Card className="border-red-200 bg-red-50">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
            <div>
              <p className="font-semibold text-red-900">Could not load review</p>
              <p className="text-sm text-red-700 mt-1">
                {(reviewError as Error).message}
              </p>
            </div>
          </div>
        </Card>
      )}

      {review && <ReviewDisplay review={review} />}
    </div>
  )
}

// ── Read-only display ────────────────────────────────────────────────────────

function ReviewDisplay({ review }: { review: ResumeReview }) {
  return (
    <div className="space-y-6">
      {/* Header card: name, headline, contact */}
      <Card>
        <h2 className="text-2xl font-bold text-slate-900">
          {review.full_name || <span className="text-slate-400">Name not detected</span>}
        </h2>
        {review.headline && (
          <p className="text-slate-600 mt-1">{review.headline}</p>
        )}
        <div className="flex flex-wrap gap-x-5 gap-y-2 mt-4 text-sm text-slate-600">
          {review.email && (
            <span className="inline-flex items-center gap-1.5">
              <Mail className="w-4 h-4 text-slate-400" /> {review.email}
            </span>
          )}
          {review.phone && (
            <span className="inline-flex items-center gap-1.5">
              <Phone className="w-4 h-4 text-slate-400" /> {review.phone}
            </span>
          )}
          {review.location && (
            <span className="inline-flex items-center gap-1.5">
              <MapPin className="w-4 h-4 text-slate-400" /> {review.location}
            </span>
          )}
          {review.linkedin && (
            <a
              href={review.linkedin.startsWith('http') ? review.linkedin : `https://${review.linkedin}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-blue-600 hover:underline"
            >
              <Linkedin className="w-4 h-4 text-slate-400" /> LinkedIn
            </a>
          )}
        </div>
      </Card>

      {/* Summary */}
      {review.summary && (
        <Card>
          <h3 className="text-lg font-semibold text-slate-900 mb-3">Summary</h3>
          <p className="text-slate-700 leading-relaxed whitespace-pre-wrap">{review.summary}</p>
        </Card>
      )}

      {/* Skills */}
      {review.skills?.length > 0 && (
        <Card>
          <h3 className="text-lg font-semibold text-slate-900 mb-3">Skills</h3>
          <div className="flex flex-wrap gap-2">
            {review.skills.map((s, i) => (
              <span
                key={i}
                className="px-2.5 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded-full text-xs font-medium"
                title={s.category ?? undefined}
              >
                {s.name}
              </span>
            ))}
          </div>
        </Card>
      )}

      {/* Experience */}
      {review.experience?.length > 0 && (
        <Card>
          <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-slate-400" /> Experience
          </h3>
          <div className="space-y-5">
            {review.experience.map((e, i) => (
              <div key={i} className="border-l-2 border-blue-200 pl-4">
                <div className="flex flex-wrap items-baseline gap-x-3">
                  <p className="font-semibold text-slate-900">{e.title}</p>
                  <p className="text-slate-600">{e.company}</p>
                  {e.location && <p className="text-slate-400 text-xs">{e.location}</p>}
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  {e.start_date ?? '?'} – {e.current ? 'Present' : (e.end_date ?? '?')}
                </p>
                {e.description && (
                  <p className="text-sm text-slate-700 mt-2 whitespace-pre-wrap">{e.description}</p>
                )}
                {e.achievements?.length ? (
                  <ul className="mt-2 space-y-1 text-sm text-slate-700">
                    {e.achievements.map((a, j) => (
                      <li key={j} className="flex gap-2"><span className="text-blue-400">•</span>{a}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Education */}
      {review.education?.length > 0 && (
        <Card>
          <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <GraduationCap className="w-5 h-5 text-slate-400" /> Education
          </h3>
          <div className="space-y-4">
            {review.education.map((ed, i) => (
              <div key={i}>
                <p className="font-semibold text-slate-900">{ed.institution}</p>
                <p className="text-sm text-slate-700">
                  {[ed.degree, ed.field].filter(Boolean).join(', ') || '—'}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {ed.start_date ?? '?'} – {ed.end_date ?? '?'}
                  {ed.gpa && <> · GPA {ed.gpa}</>}
                </p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Certifications */}
      {review.certifications?.length > 0 && (
        <Card>
          <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Award className="w-5 h-5 text-slate-400" /> Certifications
          </h3>
          <ul className="space-y-2 text-sm">
            {review.certifications.map((c, i) => (
              <li key={i}>
                <span className="font-medium text-slate-900">{c.name}</span>
                {c.issuer && <span className="text-slate-500"> · {c.issuer}</span>}
                {c.date && <span className="text-slate-400 text-xs"> · {c.date}</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Projects */}
      {review.projects?.length > 0 && (
        <Card>
          <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <FolderGit2 className="w-5 h-5 text-slate-400" /> Projects
          </h3>
          <div className="space-y-4">
            {review.projects.map((p, i) => (
              <div key={i}>
                <p className="font-semibold text-slate-900">
                  {p.url ? (
                    <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                      {p.name}
                    </a>
                  ) : p.name}
                </p>
                {p.description && (
                  <p className="text-sm text-slate-700 mt-1">{p.description}</p>
                )}
                {p.tech?.length ? (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {p.tech.map((t, j) => (
                      <span key={j} className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded text-xs">
                        {t}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </Card>
      )}

      <p className="text-xs text-slate-400 text-right">
        Last updated {new Date(review.updated_at).toLocaleString()}
      </p>
    </div>
  )
}

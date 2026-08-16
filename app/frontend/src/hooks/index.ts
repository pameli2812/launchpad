import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  setupAPI, analyzeAPI, historyAPI, settingsAPI, importsAPI,
  resumeReviewAPI, dashboardAPI, companySuggestionAPI,
  type LLMProvider,
} from '@/api/client'

// Setup hooks
export const useResumes = () => {
  return useQuery({
    queryKey: ['resumes'],
    queryFn: () => setupAPI.listResumes().then((res) => res.data.resumes),
  })
}

export const useUploadResume = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => setupAPI.uploadResume(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
    },
  })
}

export const useDeleteResume = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (resumeName: string) => setupAPI.deleteResume(resumeName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
    },
  })
}

export const useGoalSets = () => {
  return useQuery({
    queryKey: ['goalSets'],
    queryFn: () => setupAPI.listGoalSets().then((res) => res.data.goal_sets),
  })
}

export const useCreateGoalSet = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (goalSet: any) => setupAPI.createGoalSet(goalSet),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goalSets'] })
    },
  })
}

export const useDeleteGoalSet = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (goalSetId: string) => setupAPI.deleteGoalSet(goalSetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goalSets'] })
    },
  })
}

export const useActivateGoalSet = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (goalSetId: string) => setupAPI.activateGoalSet(goalSetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goalSets'] })
    },
  })
}

export const useDeactivateGoalSet = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (goalSetId: string) => setupAPI.deactivateGoalSet(goalSetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['goalSets'] })
    },
  })
}

export const useAutoInferGoals = () => {
  return useMutation({
    mutationFn: ({ resumeName, context }: { resumeName: string; context?: string }) =>
      setupAPI.autoInferGoals(resumeName, context).then((res) => res.data.goals),
  })
}

// Analysis hooks
export const useRunAnalysis = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      resumeName: string
      goalSetId: string
      jdText?: string
      jdUrl?: string
    }) => analyzeAPI.runAnalysis(params).then((res) => res.data),
    onSuccess: () => {
      // History is auto-saved server-side; refresh the list so the new entry shows up
      queryClient.invalidateQueries({ queryKey: ['history'] })
    },
  })
}

export const useGetSuggestions = () => {
  return useMutation({
    mutationFn: (params: {
      resumeName: string
      jdJson: object
      gaps: any[]
      userPrompt?: string
      override?: boolean
    }) => analyzeAPI.getSuggestions(params).then((res) => res.data.suggestions),
  })
}

export const useApplySuggestions = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      resumeName: string
      acceptedChanges: Array<{ type: string; section?: string; before?: string; after?: string }>
    }) => analyzeAPI.applySuggestions(params).then((res) => res.data),
    onSuccess: () => {
      // The revised PDF lands in the resume library — refresh it.
      queryClient.invalidateQueries({ queryKey: ['resumes'] })
    },
  })
}

// History hooks
export const useHistory = () => {
  return useQuery({
    queryKey: ['history'],
    queryFn: () => historyAPI.getHistory().then((res) => res.data.history),
  })
}

export const useAddHistoryEntry = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (entry: any) => historyAPI.addEntry(entry),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['history'] })
    },
  })
}

export const useDeleteHistoryEntry = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (entryId: string) => historyAPI.deleteEntry(entryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['history'] })
    },
  })
}

export const useSaveSuggestions = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ entryId, suggestions }: { entryId: string; suggestions: any }) =>
      historyAPI.saveSuggestions(entryId, suggestions),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['history'] })
    },
  })
}

// ── Settings: API keys ────────────────────────────────────────────────────────

export type ApiKeyRow = {
  id: string
  provider: LLMProvider
  last_4: string
  model: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export const useApiKeys = () =>
  useQuery({
    queryKey: ['api-keys'],
    queryFn: () => settingsAPI.listApiKeys().then((res) => res.data.api_keys as ApiKeyRow[]),
  })

export const useSetApiKey = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { provider: LLMProvider; api_key: string; model?: string }) =>
      settingsAPI.setApiKey(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  })
}

export const useDeleteApiKey = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (provider: LLMProvider) => settingsAPI.deleteApiKey(provider),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['api-keys'] }),
  })
}

// ── Settings: extension tokens ────────────────────────────────────────────────

export type ExtensionTokenRow = {
  id: string
  label: string
  last_4: string
  last_used_at: string | null
  revoked: boolean
  created_at: string
}

export const useExtensionTokens = () =>
  useQuery({
    queryKey: ['extension-tokens'],
    queryFn: () =>
      settingsAPI.listExtensionTokens().then((res) => res.data.tokens as ExtensionTokenRow[]),
  })

export const useCreateExtensionToken = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (label?: string) =>
      settingsAPI.createExtensionToken(label).then((res) => res.data as {
        token: string
        metadata: ExtensionTokenRow
        message: string
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['extension-tokens'] }),
  })
}

export const useRevokeExtensionToken = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (tokenId: string) => settingsAPI.revokeExtensionToken(tokenId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['extension-tokens'] }),
  })
}

// ── Imports: pending JDs from the browser extension ──────────────────────────

export type PendingImport = {
  id: string
  source: string
  url: string | null
  host: string | null
  job_id: string | null
  jd_title: string | null
  jd_text: string
  status: 'pending' | 'consumed' | 'dismissed'
  created_at: string
}

export const usePendingImports = () =>
  useQuery({
    queryKey: ['imports', 'pending'],
    queryFn: () =>
      importsAPI.listPending().then((res) => res.data.imports as PendingImport[]),
    // Poll every 10s so the Analyze page reflects new imports without a refresh.
    refetchInterval: 10_000,
    refetchOnWindowFocus: true,
  })

export const useConsumeImport = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (importId: string) => importsAPI.consume(importId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['imports', 'pending'] }),
  })
}

export const useDismissImport = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (importId: string) => importsAPI.dismiss(importId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['imports', 'pending'] }),
  })
}

// ── Resume Review ────────────────────────────────────────────────────────────

export type ResumeReview = {
  id: string
  resume_id: string
  full_name: string | null
  email: string | null
  phone: string | null
  location: string | null
  linkedin: string | null
  headline: string | null
  summary: string | null
  skills: Array<{ name: string; category?: string | null }>
  experience: Array<{
    title: string
    company: string
    location?: string | null
    start_date?: string | null
    end_date?: string | null
    current?: boolean
    description?: string | null
    achievements?: string[]
  }>
  education: Array<{
    institution: string
    degree?: string | null
    field?: string | null
    start_date?: string | null
    end_date?: string | null
    gpa?: string | null
  }>
  certifications: Array<{ name: string; issuer?: string | null; date?: string | null }>
  projects: Array<{ name: string; description?: string | null; tech?: string[]; url?: string | null }>
  created_at: string
  updated_at: string
}

export const useResumeReview = (resumeName: string | null | undefined) =>
  useQuery({
    queryKey: ['resume-review', resumeName],
    enabled:  !!resumeName,
    retry:    false,                         // 404 = "no review yet" — don't retry
    queryFn:  () =>
      resumeReviewAPI.get(resumeName!).then((res) => res.data.review as ResumeReview),
  })

export const useExtractResumeReview = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (resumeName: string) =>
      resumeReviewAPI.extract(resumeName).then((res) => res.data.review as ResumeReview),
    onSuccess: (_, resumeName) => {
      qc.invalidateQueries({ queryKey: ['resume-review', resumeName] })
    },
  })
}

export const usePatchResumeReview = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { resumeName: string; patch: Partial<ResumeReview> }) =>
      resumeReviewAPI.patch(params.resumeName, params.patch).then((r) => r.data.review as ResumeReview),
    onSuccess: (_, params) => {
      qc.invalidateQueries({ queryKey: ['resume-review', params.resumeName] })
    },
  })
}

// ── Dashboard ────────────────────────────────────────────────────────────────

export type DashboardData = {
  totals:   { resumes: number; goal_sets: number; analyses: number; avg_fit: number | null }
  verdicts: { apply: number; borderline: number; skip: number }
  timeline: Array<{
    analyzed_at: string
    overall_fit: number
    verdict:     string
    jd_title:    string | null
    company:     string | null
    jd_id:       string
  }>
  gap_types:   Array<{ type: string; count: number }>
  top_resumes: Array<{ filename: string; count: number }>
}

export const useDashboard = () =>
  useQuery({
    queryKey: ['dashboard'],
    queryFn:  () => dashboardAPI.get().then((res) => res.data as DashboardData),
  })

// ── Company Suggestion ───────────────────────────────────────────────────────

export type CompanyCard = {
  name: string
  industry: string | null
  size: 'startup' | 'small' | 'mid' | 'large' | 'enterprise' | null
  location: string | null
  remote_policy: 'remote' | 'hybrid' | 'onsite' | 'varies' | null
  website: string | null
  description: string
  why_fit: string
  focus_areas: string[]
  hiring_likelihood: 'high' | 'medium' | 'low'
  match_score: number
}

export type CompanySuggestion = {
  id: string
  resume_id: string
  companies: CompanyCard[]
  user_prompt: string | null
  created_at: string
  updated_at: string
}

export const useCompanySuggestion = (resumeName: string | null | undefined) =>
  useQuery({
    queryKey: ['company-suggestion', resumeName],
    enabled:  !!resumeName,
    retry:    false,
    queryFn:  () =>
      companySuggestionAPI.get(resumeName!).then((r) => r.data.suggestion as CompanySuggestion),
  })

export const useGenerateCompanySuggestion = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { resumeName: string; userPrompt?: string }) =>
      companySuggestionAPI.generate(params.resumeName, params.userPrompt)
        .then((r) => r.data.suggestion as CompanySuggestion),
    onSuccess: (_, params) => {
      qc.invalidateQueries({ queryKey: ['company-suggestion', params.resumeName] })
    },
  })
}

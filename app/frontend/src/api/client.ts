import axios from 'axios'

// Vite's import.meta.env typings for this file to avoid
// "Property 'env' does not exist on type 'ImportMeta'" errors.
declare global {
  interface ImportMetaEnv {
    VITE_API_URL?: string
    // add other env variables here as needed
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv
  }
}

// const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api'
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,   // carry the httpOnly refresh cookie on /api/auth/*
})

// Inject the bearer token from localStorage on every request.
// Auth.tsx stores the access token under 'lp_access_token' on signup/login;
// any axios call through this client picks it up automatically.
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('lp_access_token')
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

// 401 auto-refresh.
// JWT access tokens expire after ACCESS_TOKEN_EXPIRE_MINUTES (default 15);
// the long-lived refresh token lives in an httpOnly cookie scoped to /api/auth.
// When any authed call comes back 401, we hit POST /api/auth/refresh — that
// reads the cookie, returns a new access_token + rotates the refresh cookie —
// then retry the original request. A module-level single-flight Promise stops
// N parallel 401s from triggering N parallel refresh calls.
//
// If refresh itself fails (refresh cookie expired/revoked), we clear the
// stored token + user and reload, which surfaces AuthGate.
let refreshInFlight: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    try {
      const resp = await axios.post(`${API_BASE_URL}/auth/refresh`, null, {
        withCredentials: true,
      })
      const t = resp.data?.access_token as string | undefined
      if (t) {
        localStorage.setItem('lp_access_token', t)
        return t
      }
      return null
    } catch {
      return null
    } finally {
      // Clear the in-flight promise after one tick so other listeners that
      // awaited it can read it cleanly first.
      setTimeout(() => { refreshInFlight = null }, 0)
    }
  })()
  return refreshInFlight
}

apiClient.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config as (typeof error.config) & { _retried?: boolean }
    const status = error.response?.status

    // Don't try to refresh the refresh endpoint itself (would loop)
    if (status !== 401 || !original || original._retried ||
        original.url?.includes('/auth/refresh') ||
        original.url?.includes('/auth/login') ||
        original.url?.includes('/auth/signup')) {
      throw error
    }

    original._retried = true
    const newToken = await refreshAccessToken()

    if (!newToken) {
      // Refresh failed — fully expired session. Surface AuthGate.
      localStorage.removeItem('lp_access_token')
      localStorage.removeItem('lp_user')
      if (typeof window !== 'undefined') window.location.reload()
      throw error
    }

    original.headers.set('Authorization', `Bearer ${newToken}`)
    return apiClient.request(original)
  },
)

// Setup endpoints
export const setupAPI = {
  uploadResume: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post('/setup/upload-resume', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  listResumes: () => apiClient.get('/setup/resumes'),
  deleteResume: (resumeName: string) => apiClient.delete(`/setup/resume/${encodeURIComponent(resumeName)}`),
  getResumeViewUrl: (resumeName: string) =>
    `${API_BASE_URL}/setup/resume/${encodeURIComponent(resumeName)}/view`,
  
  listGoalSets: () => apiClient.get('/setup/goal-sets'),
  createGoalSet: (goalSet: any) => apiClient.post('/setup/goal-sets', goalSet),
  deleteGoalSet: (goalSetId: string) => apiClient.delete(`/setup/goal-sets/${goalSetId}`),
  activateGoalSet: (goalSetId: string) =>
    apiClient.post(`/setup/goal-sets/${goalSetId}/activate`),
  deactivateGoalSet: (goalSetId: string) =>
    apiClient.post(`/setup/goal-sets/${goalSetId}/deactivate`),
  autoInferGoals: (resumeName: string, context?: string) =>
    apiClient.post('/setup/goal-sets/auto-infer', { resume_name: resumeName, context }),
}

// Analysis endpoints
// export const analyzeAPI = {
//   runAnalysis: (resumeId: string, goalSetId: string, jd: string) =>
//     apiClient.post('/analyze/run', { resume_id: resumeId, goal_set_id: goalSetId, job_description: jd }),
  
//   calculateScore: (resumeText: string, jdText: string, goalDesc?: string) =>
//     apiClient.post('/analyze/score', { resume_text: resumeText, job_description: jdText, goal_description: goalDesc }),
  
//   getSuggestions: (resumeText: string, jdText: string, gaps?: any) =>
//     apiClient.post('/analyze/suggestions', { resume_text: resumeText, job_description: jdText, analysis_gaps: gaps }),
// }

export const analyzeAPI = {
  runAnalysis: (params: {
    resumeName: string
    goalSetId: string
    jdText?: string
    jdUrl?: string
  }) =>
    apiClient.post('/analyze/run', {
      resume_name: params.resumeName,
      goal_set_id: params.goalSetId,
      jd_text: params.jdText,
      jd_url: params.jdUrl,
    }),

  getSuggestions: (params: {
    resumeName: string
    jdJson: object
    gaps: any[]
    userPrompt?: string
    override?: boolean
  }) =>
    apiClient.post('/analyze/suggestions', {
      resume_name: params.resumeName,
      jd_json: params.jdJson,
      gaps: params.gaps,
      user_prompt: params.userPrompt,
      override: params.override ?? false,
    }),

  applySuggestions: (params: {
    resumeName: string
    acceptedChanges: Array<{ type: string; section?: string; before?: string; after?: string }>
  }) =>
    apiClient.post('/analyze/apply-suggestions', {
      resume_name: params.resumeName,
      accepted_changes: params.acceptedChanges,
    }),

  getDownloadUrl: (revisedFilename: string) =>
    `${API_BASE_URL}/analyze/download/${encodeURIComponent(revisedFilename)}`,
}

// History endpoints
export const historyAPI = {
  getHistory: () => apiClient.get('/history/'),
  getEntry: (entryId: string) => apiClient.get(`/history/${entryId}`),
  addEntry: (entry: any) => apiClient.post('/history/', entry),
  deleteEntry: (entryId: string) => apiClient.delete(`/history/${entryId}`),
  saveSuggestions: (entryId: string, suggestions: any) =>
    apiClient.post(`/history/${entryId}/suggestions`, suggestions),
}

// Settings — per-user LLM API keys + browser-extension tokens
export type LLMProvider = 'anthropic' | 'openai' | 'gemini'

export const settingsAPI = {
  listApiKeys: () => apiClient.get('/settings/api-keys'),
  setApiKey: (params: { provider: LLMProvider; api_key: string; model?: string }) =>
    apiClient.put('/settings/api-keys', params),
  deleteApiKey: (provider: LLMProvider) =>
    apiClient.delete(`/settings/api-keys/${provider}`),

  listExtensionTokens: () => apiClient.get('/settings/extension-tokens'),
  createExtensionToken: (label?: string) =>
    apiClient.post('/settings/extension-tokens', { label: label ?? 'Browser extension' }),
  revokeExtensionToken: (tokenId: string) =>
    apiClient.delete(`/settings/extension-tokens/${tokenId}`),
}

// Imports — JDs sent in from the browser extension
export const importsAPI = {
  listPending: () => apiClient.get('/imports/pending'),
  consume:  (importId: string) => apiClient.post(`/imports/${importId}/consume`),
  dismiss:  (importId: string) => apiClient.post(`/imports/${importId}/dismiss`),
}

// Resume Review — LLM-extracted structured profile per resume
export const resumeReviewAPI = {
  get:     (resumeName: string) =>
    apiClient.get(`/resume-review/${encodeURIComponent(resumeName)}`),
  extract: (resumeName: string) =>
    apiClient.post(`/resume-review/${encodeURIComponent(resumeName)}/extract`),
  patch:   (resumeName: string, patch: object) =>
    apiClient.patch(`/resume-review/${encodeURIComponent(resumeName)}`, patch),
  delete:  (resumeName: string) =>
    apiClient.delete(`/resume-review/${encodeURIComponent(resumeName)}`),
}

// Dashboard — aggregate stats for the overview page
export const dashboardAPI = {
  get: () => apiClient.get('/dashboard'),
}

// Company Suggestion — LLM-curated target companies per resume
export const companySuggestionAPI = {
  get: (resumeName: string) =>
    apiClient.get(`/company-suggestion/${encodeURIComponent(resumeName)}`),
  generate: (resumeName: string, userPrompt?: string) =>
    apiClient.post(`/company-suggestion/${encodeURIComponent(resumeName)}/generate`, {
      user_prompt: userPrompt ?? null,
    }),
  delete: (resumeName: string) =>
    apiClient.delete(`/company-suggestion/${encodeURIComponent(resumeName)}`),
}

export default apiClient

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
})

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

export default apiClient

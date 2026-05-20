import axios from 'axios'

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api'

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
  deleteResume: (resumeName: string) => apiClient.delete(`/setup/resume/${resumeName}`),
  
  listGoalSets: () => apiClient.get('/setup/goal-sets'),
  createGoalSet: (goalSet: any) => apiClient.post('/setup/goal-sets', goalSet),
  deleteGoalSet: (goalSetId: string) => apiClient.delete(`/setup/goal-sets/${goalSetId}`),
}

// Analysis endpoints
export const analyzeAPI = {
  runAnalysis: (resumeId: string, goalSetId: string, jd: string) =>
    apiClient.post('/analyze/run', { resume_id: resumeId, goal_set_id: goalSetId, job_description: jd }),
  
  calculateScore: (resumeText: string, jdText: string, goalDesc?: string) =>
    apiClient.post('/analyze/score', { resume_text: resumeText, job_description: jdText, goal_description: goalDesc }),
  
  getSuggestions: (resumeText: string, jdText: string, gaps?: any) =>
    apiClient.post('/analyze/suggestions', { resume_text: resumeText, job_description: jdText, analysis_gaps: gaps }),
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

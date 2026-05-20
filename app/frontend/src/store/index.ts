import { create } from 'zustand'

interface Resume {
  filename: string
  size: number
  extracted_text: string
}

interface GoalSet {
  id: string
  name: string
  goals: any[]
}

interface AppState {
  // Resume management
  selectedResume: Resume | null
  resumes: Resume[]
  setSelectedResume: (resume: Resume | null) => void
  setResumes: (resumes: Resume[]) => void
  
  // Goal set management
  selectedGoalSet: GoalSet | null
  goalSets: GoalSet[]
  setSelectedGoalSet: (goalSet: GoalSet | null) => void
  setGoalSets: (goalSets: GoalSet[]) => void
  
  // Analysis state
  analysisResult: any | null
  setAnalysisResult: (result: any) => void
  
  // UI state
  currentTab: 'setup' | 'analyze' | 'history'
  setCurrentTab: (tab: 'setup' | 'analyze' | 'history') => void
}

export const useAppStore = create<AppState>((set) => ({
  selectedResume: null,
  resumes: [],
  setSelectedResume: (resume) => set({ selectedResume: resume }),
  setResumes: (resumes) => set({ resumes }),
  
  selectedGoalSet: null,
  goalSets: [],
  setSelectedGoalSet: (goalSet) => set({ selectedGoalSet: goalSet }),
  setGoalSets: (goalSets) => set({ goalSets }),
  
  analysisResult: null,
  setAnalysisResult: (result) => set({ analysisResult: result }),
  
  currentTab: 'analyze',
  setCurrentTab: (tab) => set({ currentTab: tab }),
}))

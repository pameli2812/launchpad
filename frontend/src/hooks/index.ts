import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { setupAPI, analyzeAPI, historyAPI } from '@/api/client'

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

// Analysis hooks
export const useRunAnalysis = () => {
  return useMutation({
    mutationFn: ({ resumeId, goalSetId, jd }: { resumeId: string; goalSetId: string; jd: string }) =>
      analyzeAPI.runAnalysis(resumeId, goalSetId, jd),
  })
}

export const useCalculateScore = () => {
  return useMutation({
    mutationFn: ({ resumeText, jdText, goalDesc }: { resumeText: string; jdText: string; goalDesc?: string }) =>
      analyzeAPI.calculateScore(resumeText, jdText, goalDesc),
  })
}

export const useGetSuggestions = () => {
  return useMutation({
    mutationFn: ({ resumeText, jdText, gaps }: { resumeText: string; jdText: string; gaps?: any }) =>
      analyzeAPI.getSuggestions(resumeText, jdText, gaps),
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

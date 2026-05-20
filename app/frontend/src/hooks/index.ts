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

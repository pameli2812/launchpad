import { useRunAnalysis, useGetSuggestions } from '@/hooks'
import { Button, Card, Input, Select } from './UI'
import { Play, AlertCircle, CheckCircle } from 'lucide-react'
import { useState } from 'react'

export function AnalyzePage() {
  const [selectedResume, setSelectedResume] = useState('')
  const [selectedGoal, setSelectedGoal] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [analysisResult, setAnalysisResult] = useState<any>(null)

  const { mutate: runAnalysis, isPending: analyzing } = useRunAnalysis()
  const { mutate: getSuggestions, isPending: generatingSuggestions } = useGetSuggestions()

  const handleAnalyze = () => {
    if (selectedResume && selectedGoal && jobDescription) {
      runAnalysis(
        { resumeId: selectedResume, goalSetId: selectedGoal, jd: jobDescription },
        {
          onSuccess: (data) => {
            setAnalysisResult(data.data)
          },
        }
      )
    }
  }

  const handleGetSuggestions = () => {
    if (analysisResult) {
      getSuggestions(
        { resumeText: selectedResume, jdText: jobDescription, gaps: analysisResult?.gaps },
        {
          onSuccess: (data) => {
            setAnalysisResult({ ...analysisResult, suggestions: data.data.suggestions })
          },
        }
      )
    }
  }

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      {/* Header */}
      <div className="flex justify-between items-end border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Analyze</h1>
          <p className="text-slate-500 mt-1 text-sm">Compare your resume against job requirements</p>
        </div>
      </div>

      {!analysisResult ? (
        /* Input Section */
        <Card>
          <h2 className="text-xl font-semibold text-slate-900 mb-6">New Analysis</h2>
          <div className="space-y-6">
            <Select
              label="📄 Resume"
              options={[{ value: 'resume-1', label: 'Sample Resume' }]}
              value={selectedResume}
              onChange={(e) => setSelectedResume(e.target.value)}
            />
            
            <Select
              label="🎯 Goal Set"
              options={[{ value: 'goal-1', label: 'Senior Engineer' }]}
              value={selectedGoal}
              onChange={(e) => setSelectedGoal(e.target.value)}
            />
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Job Description</label>
              <textarea
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Paste the job description here..."
                rows={8}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <Button onClick={handleAnalyze} loading={analyzing} className="w-full">
              <Play className="w-4 h-4 inline mr-2" />
              Run Analysis
            </Button>
          </div>
        </Card>
      ) : (
        /* Results Section */
        <div className="space-y-6">
          {/* Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <div className="text-sm font-medium text-slate-500 uppercase">Overall Match</div>
              <div className="text-4xl font-bold text-blue-600 mt-2">
                {analysisResult?.score || 85}%
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-500 uppercase">Gaps Found</div>
              <div className="text-4xl font-bold text-amber-600 mt-2">
                {analysisResult?.gaps?.length || 0}
              </div>
            </Card>
            <Card>
              <div className="text-sm font-medium text-slate-500 uppercase">Ready to Apply</div>
              <div className={`text-lg font-semibold mt-2 ${(analysisResult?.score || 85) >= 80 ? 'text-green-600' : 'text-orange-600'}`}>
                {(analysisResult?.score || 85) >= 80 ? '✓ Yes' : '⚠ Review'}
              </div>
            </Card>
          </div>

          {/* Gaps */}
          {analysisResult?.gaps && analysisResult.gaps.length > 0 && (
            <Card className="border-l-4 border-amber-500">
              <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-amber-600" />
                Gaps to Address
              </h3>
              <div className="space-y-3">
                {analysisResult.gaps.map((gap: any, idx: number) => (
                  <div key={idx} className="p-3 bg-slate-50 rounded border border-slate-200">
                    <div className="font-medium text-slate-900">{gap.title}</div>
                    <div className="text-sm text-slate-600 mt-1">{gap.description}</div>
                    <div className="text-xs font-semibold mt-2 inline-block px-2 py-1 rounded bg-amber-100 text-amber-700">
                      {gap.criticality || 'Medium'}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Suggestions */}
          {analysisResult?.suggestions && (
            <Card className="border-l-4 border-green-500">
              <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-600" />
                Suggestions
              </h3>
              <div className="space-y-3">
                {analysisResult.suggestions.map((sugg: any, idx: number) => (
                  <div key={idx} className="p-3 bg-slate-50 rounded border border-slate-200">
                    <div className="font-medium text-slate-900">{sugg.title}</div>
                    <div className="text-sm text-slate-600 mt-1">{sugg.description}</div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3">
            {!analysisResult?.suggestions && (
              <Button onClick={handleGetSuggestions} loading={generatingSuggestions}>
                Generate Suggestions
              </Button>
            )}
            <Button variant="secondary" onClick={() => setAnalysisResult(null)}>
              Start New Analysis
            </Button>
            <Button>💾 Save to History</Button>
          </div>
        </div>
      )}
    </div>
  )
}

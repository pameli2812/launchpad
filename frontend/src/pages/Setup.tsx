import { useResumes, useUploadResume, useGoalSets, useCreateGoalSet } from '@/hooks'
import { Button, Card, Input } from './UI'
import { Upload, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

export function SetupPage() {
  const [showCreateGoal, setShowCreateGoal] = useState(false)
  const [goalName, setGoalName] = useState('')
  
  const { data: resumes = [], isLoading: resumesLoading } = useResumes()
  const { mutate: uploadResume, isPending: uploading } = useUploadResume()
  const { data: goalSets = [] } = useGoalSets()
  const { mutate: createGoalSet, isPending: creatingGoal } = useCreateGoalSet()

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      uploadResume(file)
    }
  }

  const handleCreateGoal = () => {
    if (goalName.trim()) {
      createGoalSet({ name: goalName, goals: [] })
      setGoalName('')
      setShowCreateGoal(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-12">
      {/* Step 1: Resumes */}
      <section>
        <div className="flex justify-between items-end border-b border-slate-200 pb-6 mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Step 1: Resumes</h2>
            <p className="text-slate-500 text-sm mt-1">Upload and manage your resumes</p>
          </div>
        </div>

        <div className="mb-8">
          <label htmlFor="file-upload" className="flex items-center justify-center gap-2 cursor-pointer">
            <Card className="w-full border-2 border-dashed border-slate-300 hover:border-slate-400 transition-colors p-8">
              <div className="text-center">
                <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                <p className="text-slate-600 font-medium">Click to upload resume (PDF or DOCX)</p>
                <input
                  id="file-upload"
                  type="file"
                  accept=".pdf,.docx"
                  onChange={handleFileUpload}
                  className="hidden"
                  disabled={uploading}
                />
              </div>
            </Card>
          </label>
        </div>

        {/* Resumes Table */}
        {resumesLoading ? (
          <p className="text-slate-500">Loading resumes...</p>
        ) : (
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <div className="grid grid-cols-4 bg-slate-100 border-b border-slate-200">
              <div className="p-4 font-semibold text-slate-900">File Name</div>
              <div className="p-4 font-semibold text-slate-900 text-center">Size</div>
              <div className="p-4 font-semibold text-slate-900 text-center">View</div>
              <div className="p-4 font-semibold text-slate-900 text-center">Delete</div>
            </div>
            {resumes.length === 0 ? (
              <div className="p-8 text-center text-slate-500">No resumes uploaded yet</div>
            ) : (
              resumes.map((resume: any, idx: number) => (
                <div key={idx} className="grid grid-cols-4 border-b border-slate-200 hover:bg-slate-50">
                  <div className="p-4 text-slate-900">{resume.filename}</div>
                  <div className="p-4 text-slate-600 text-center">{Math.round(resume.size / 1024)} KB</div>
                  <div className="p-4 text-center">
                    <Button variant="secondary" size="sm">👁️</Button>
                  </div>
                  <div className="p-4 text-center">
                    <Button variant="danger" size="sm">🗑️</Button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </section>

      {/* Step 2: Goals */}
      <section>
        <div className="flex justify-between items-end border-b border-slate-200 pb-6 mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Step 2: Goals</h2>
            <p className="text-slate-500 text-sm mt-1">Define your career goals</p>
          </div>
        </div>

        {/* Goal Sets Table */}
        {goalSets.length === 0 ? (
          <p className="text-slate-500 mb-6">No goal sets created yet</p>
        ) : (
          <div className="border border-slate-200 rounded-lg overflow-hidden mb-6">
            <div className="grid grid-cols-5 bg-slate-100 border-b border-slate-200">
              <div className="p-4 font-semibold text-slate-900">Goal Set</div>
              <div className="p-4 font-semibold text-slate-900 text-center"># Goals</div>
              <div className="p-4 font-semibold text-slate-900 text-center">Created</div>
              <div className="p-4 font-semibold text-slate-900 text-center">View</div>
              <div className="p-4 font-semibold text-slate-900 text-center">Delete</div>
            </div>
            {goalSets.map((goalSet: any, idx: number) => (
              <div key={idx} className="grid grid-cols-5 border-b border-slate-200 hover:bg-slate-50">
                <div className="p-4 text-slate-900 font-medium">{goalSet.name}</div>
                <div className="p-4 text-slate-600 text-center">{goalSet.goals?.length || 0}</div>
                <div className="p-4 text-slate-600 text-center text-sm">{new Date(goalSet.created_at).toLocaleDateString()}</div>
                <div className="p-4 text-center">
                  <Button variant="secondary" size="sm">👁️</Button>
                </div>
                <div className="p-4 text-center">
                  <Button variant="danger" size="sm">🗑️</Button>
                </div>
              </div>
            ))}
          </div>
        )}

        {!showCreateGoal ? (
          <Button onClick={() => setShowCreateGoal(true)}>
            <Plus className="w-4 h-4 inline mr-2" />
            Add New Goal Set
          </Button>
        ) : (
          <Card className="border-blue-300 bg-blue-50">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">Create New Goal Set</h3>
            <div className="space-y-4">
              <Input
                label="Goal Set Name"
                placeholder="e.g., Senior Engineer at Tech Company"
                value={goalName}
                onChange={(e) => setGoalName(e.target.value)}
              />
              <div className="flex gap-2">
                <Button onClick={handleCreateGoal} loading={creatingGoal}>
                  Create
                </Button>
                <Button variant="secondary" onClick={() => setShowCreateGoal(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          </Card>
        )}
      </section>
    </div>
  )
}

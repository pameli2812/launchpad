import { useHistory, useDeleteHistoryEntry } from '@/hooks'
import { Button, Card } from './UI'
import { Trash2, Eye } from 'lucide-react'

export function HistoryPage() {
  const { data: history = [], isLoading } = useHistory()
  const { mutate: deleteEntry } = useDeleteHistoryEntry()

  if (isLoading) {
    return <div className="max-w-6xl mx-auto p-8 text-slate-500">Loading history...</div>
  }

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-8">
      <div className="border-b border-slate-200 pb-6">
        <h1 className="text-3xl font-bold text-slate-900">Analysis History</h1>
        <p className="text-slate-500 mt-1 text-sm">Your past analyses and suggestions</p>
      </div>

      {history.length === 0 ? (
        <Card className="text-center p-12">
          <p className="text-slate-500">No analysis history yet</p>
          <p className="text-slate-400 text-sm mt-2">Run your first analysis to get started</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {history.map((entry: any, idx: number) => (
            <Card key={idx} className="hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-slate-900">
                    Analysis #{history.length - idx}
                  </h3>
                  <p className="text-slate-600 text-sm mt-1">
                    {entry.resume_filename || 'Unknown Resume'} • {entry.goal_set_name || 'Unknown Goal'}
                  </p>
                  <p className="text-slate-500 text-xs mt-2">
                    {new Date(entry.created_at).toLocaleString()}
                  </p>
                </div>
                
                <div className="flex items-center gap-2">
                  {entry.score && (
                    <div className="text-right mr-4">
                      <div className="text-2xl font-bold text-blue-600">{entry.score}%</div>
                      <div className="text-xs text-slate-500">Match Score</div>
                    </div>
                  )}
                  
                  <Button variant="secondary" size="sm">
                    <Eye className="w-4 h-4" />
                  </Button>
                  <Button 
                    variant="danger" 
                    size="sm"
                    onClick={() => deleteEntry(entry.id)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {entry.suggestions && (
                <div className="mt-4 pt-4 border-t border-slate-200">
                  <p className="text-sm font-medium text-slate-700 mb-2">Suggestions:</p>
                  <ul className="text-sm text-slate-600 space-y-1">
                    {entry.suggestions.slice(0, 3).map((sugg: any, i: number) => (
                      <li key={i}>• {sugg.title || sugg}</li>
                    ))}
                    {entry.suggestions.length > 3 && (
                      <li className="text-slate-500 italic">... and {entry.suggestions.length - 3} more</li>
                    )}
                  </ul>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

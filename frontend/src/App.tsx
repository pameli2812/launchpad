import { useState } from 'react'
import { useAppStore } from '@/store'
import { SetupPage } from '@/pages/Setup'
import { AnalyzePage } from '@/pages/Analyze'
import { HistoryPage } from '@/pages/History'
import { GraduationCap, FileText, Clock } from 'lucide-react'

function App() {
  const { currentTab, setCurrentTab } = useAppStore()

  const tabs = [
    { id: 'setup', label: 'Setup', icon: GraduationCap },
    { id: 'analyze', label: 'Analyze', icon: FileText },
    { id: 'history', label: 'History', icon: Clock },
  ] as const

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-8 py-6">
          <div className="flex items-center gap-3 mb-6">
            <GraduationCap className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-slate-900">Launchpad</h1>
            <p className="text-slate-500 text-sm ml-auto">Resume AI Analyzer</p>
          </div>
          
          {/* Tabs */}
          <div className="flex gap-1">
            {tabs.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setCurrentTab(id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                  currentTab === id
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="py-8">
        {currentTab === 'setup' && <SetupPage />}
        {currentTab === 'analyze' && <AnalyzePage />}
        {currentTab === 'history' && <HistoryPage />}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 mt-16 py-8">
        <div className="max-w-7xl mx-auto px-8 text-center text-slate-500 text-sm">
          <p>Launchpad • Resume Analysis & Optimization • 2026</p>
        </div>
      </footer>
    </div>
  )
}

export default App

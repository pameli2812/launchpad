import { useAppStore, type TabId } from '@/store'
import { SetupPage } from '@/pages/Setup'
import { AnalyzePage } from '@/pages/Analyze'
import { HistoryPage } from '@/pages/History'
import { SettingsPage } from '@/pages/Settings'
import { ResumeReviewPage } from '@/pages/ResumeReview'
import { DashboardPage } from '@/pages/Dashboard'
import { CompanySuggestionPage } from '@/pages/CompanySuggestion'
import {
  FileText, Clock, Settings, LayoutDashboard, ClipboardList, Briefcase,
  User, Building2, BarChart3,
} from 'lucide-react'
import { AuthGate, UserMenu } from '@/pages/Auth'
import { ATSRank } from '@/components/ATSRank'
import { useResumes } from '@/hooks'
import { useState, useEffect } from 'react'
import { Card } from '@/components/UI'

// ── Logo ──────────────────────────────────────────────────────────────────────

function LaunchpadLogo() {
  return (
    <svg width="182" height="36" viewBox="0 0 182 36" fill="none" xmlns="http://www.w3.org/2000/svg">
      <polygon points="18,2 28,8 28,24 18,30 8,24 8,8" fill="#2563eb"/>
      <polygon points="18,2 28,8 28,24 18,30 8,24 8,8" fill="none" stroke="#1d4ed8" strokeWidth="0.75"/>
      <polygon points="18,7 25,11 25,21 18,25 11,21 11,11" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="0.75"/>
      <rect x="14.5" y="13" width="7" height="10" rx="3.5" fill="white"/>
      <path d="M14.5,16 Q14.5,8 18,6 Q21.5,8 21.5,16 Z" fill="white"/>
      <circle cx="18" cy="16.5" r="2.2" fill="#bfdbfe"/>
      <circle cx="18" cy="16.5" r="1.3" fill="#2563eb"/>
      <circle cx="17" cy="15.5" r="0.5" fill="rgba(255,255,255,0.7)"/>
      <path d="M14.5,19.5 L10.5,24 L14.5,22.5 Z" fill="#93c5fd"/>
      <path d="M21.5,19.5 L25.5,24 L21.5,22.5 Z" fill="#93c5fd"/>
      <rect x="15.8" y="23" width="4.4" height="2" rx="1" fill="#bfdbfe"/>
      <ellipse cx="18" cy="27" rx="2.2" ry="3" fill="#fbbf24"/>
      <ellipse cx="18" cy="28.5" rx="1.2" ry="2" fill="#f97316"/>
      <ellipse cx="18" cy="29.8" rx="0.6" ry="1" fill="#fef9c3"/>
      <text x="36" y="24" fontFamily="system-ui,-apple-system,sans-serif" fontSize="22" fontWeight="700" letterSpacing="-0.5">
        <tspan fill="#0f172a">Launch</tspan><tspan fill="#2563eb">pad</tspan>
      </text>
    </svg>
  )
}

// ── Nav config ────────────────────────────────────────────────────────────────
// Top-level modules — independent ones (Dashboard, Settings) have a single tab
// equal to their own ID, which renders the sub-tab strip as empty (and the UI
// hides that row in that case). Grouped modules expose their sub-tabs.

type ModuleConfig = {
  id: string
  label: string
  icon: typeof FileText
  tabs: { id: TabId; label: string; icon: typeof FileText }[]
}

const MODULES: ModuleConfig[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: LayoutDashboard,
    tabs: [
      { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    ],
  },
  {
    id: 'job-analysis',
    label: 'Job Analysis',
    icon: Briefcase,
    tabs: [
      { id: 'analyze', label: 'Analyze', icon: FileText },
      { id: 'setup',   label: 'Setup',   icon: Settings },
      { id: 'history', label: 'History', icon: Clock },
    ],
  },
  {
    id: 'resume-builder',
    label: 'Resume Builder',
    icon: User,
    tabs: [
      { id: 'resume-review',      label: 'Resume Review',      icon: ClipboardList },
      { id: 'ats-rank',           label: 'ATS Rank',           icon: BarChart3 },
      { id: 'company-suggestion', label: 'Company Suggestion', icon: Building2 },
    ],
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    tabs: [
      { id: 'settings', label: 'Settings', icon: Settings },
    ],
  },
]

// ── ATS Rank Page ─────────────────────────────────────────────────────────────

function AtsRankPage() {
  const { data: resumes = [], isLoading: resumesLoading } = useResumes()
  const setCurrentTab = useAppStore((s) => s.setCurrentTab)
  const [selectedResume, setSelectedResume] = useState<string>('')

  useEffect(() => {
    if (!selectedResume && resumes.length > 0) {
      setSelectedResume(resumes[0].name)
    }
  }, [resumes, selectedResume])

  // Show empty state if there are no resumes
  if (resumesLoading) {
    return <div className="max-w-6xl mx-auto p-8 text-slate-500">Loading…</div>
  }

  if (resumes.length === 0) {
    return (
      <div className="max-w-6xl mx-auto p-8">
        <div className="border-b border-slate-200 pb-6 mb-8">
          <h1 className="text-3xl font-bold text-slate-900">ATS Rank</h1>
        </div>
        <Card className="text-center py-16">
          <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-700 font-semibold text-lg">No resumes yet</p>
          <p className="text-slate-400 text-sm mt-2 mb-5">
            Upload a resume in Setup, then come back here to analyze ATS compatibility.
          </p>
          <button
            onClick={() => setCurrentTab('setup')}
            className="px-4 py-2 rounded-lg font-medium bg-blue-600 hover:bg-blue-700 text-white"
          >
            Go to Setup
          </button>
        </Card>
      </div>
    )
  }

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div className="max-w-6xl mx-auto px-8 pt-8 border-b border-slate-200 pb-6">
        <h1 className="text-3xl font-bold text-slate-900">ATS Rank</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Score how your resume parses against common ATS engines like Greenhouse, Lever, and Workday.
        </p>
      </div>

      {/* Resume selector */}
      <div className="max-w-6xl mx-auto px-8">
        <Card>
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-700 mb-2">Resume</label>
              <select
                value={selectedResume}
                onChange={(e) => setSelectedResume(e.target.value)}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                {resumes.map((r: { name: string }) => (
                  <option key={r.name} value={r.name}>{r.name}</option>
                ))}
              </select>
            </div>
          </div>
        </Card>
      </div>

      {/* ATS Analysis */}
      <div className="max-w-6xl mx-auto px-8 pb-8">
        {selectedResume && <ATSRank resumeId={selectedResume} />}
      </div>
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────

function App() {
  const { currentTab, setCurrentTab } = useAppStore()

  // Resolve which module owns the active tab
  const activeModule =
    MODULES.find((m) => m.tabs.some((t) => t.id === currentTab)) ?? MODULES[0]

  const handleModuleClick = (mod: ModuleConfig) => {
    // Jump to the first sub-tab in the module — for single-tab modules
    // (Dashboard / Settings) that IS the module's only tab
    setCurrentTab(mod.tabs[0].id)
  }

  // Hide the sub-tab row when there's nothing to choose between
  const showSubTabs = activeModule.tabs.length > 1

  return (
    <AuthGate>
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">

      {/* ── Header ───────────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-8">

          {/* Row 1 — logo + module switcher + user menu */}
          <div className="flex items-center gap-6 py-4 border-b border-slate-100">
            <LaunchpadLogo />

            <nav className="flex items-center gap-1 bg-slate-100 rounded-xl p-1 ml-4">
              {MODULES.map((mod) => {
                const Icon = mod.icon
                const isActive = activeModule.id === mod.id
                return (
                  <button
                    key={mod.id}
                    onClick={() => handleModuleClick(mod)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold whitespace-nowrap transition-all ${
                      isActive
                        ? 'bg-white text-slate-900 shadow-sm'
                        : 'text-slate-500 hover:text-slate-700'
                    }`}
                  >
                    <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                    {mod.label}
                    {isActive && (
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-500 ml-0.5" />
                    )}
                  </button>
                )
              })}
            </nav>

            <p className="text-slate-400 text-sm ml-auto">Resume AI Analyzer</p>
            <UserMenu />
          </div>

          {/* Row 2 — sub-tabs for the active module (hidden for single-tab modules) */}
          {showSubTabs && (
            <div className="flex items-center gap-1 py-2.5 overflow-x-auto">
              <span className="text-xs text-slate-400 mr-2 font-medium">
                {activeModule.label}
              </span>
              <span className="text-slate-200 mr-2 text-sm">›</span>
              {activeModule.tabs.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setCurrentTab(id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                    currentTab === id
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      {/* ── Content ──────────────────────────────────────────────────────────── */}
      <main className="py-8">
        {currentTab === 'dashboard'          && <DashboardPage />}
        {currentTab === 'analyze'            && <AnalyzePage />}
        {currentTab === 'setup'              && <SetupPage />}
        {currentTab === 'history'            && <HistoryPage />}
        {currentTab === 'resume-review'      && <ResumeReviewPage />}
        {currentTab === 'ats-rank'           && <AtsRankPage />}
        {currentTab === 'company-suggestion' && <CompanySuggestionPage />}
        {currentTab === 'settings'           && <SettingsPage />}
      </main>

      {/* ── Footer ───────────────────────────────────────────────────────────── */}
      <footer className="bg-white border-t border-slate-200 mt-16 py-6">
        <div className="max-w-7xl mx-auto px-8 text-center text-slate-400 text-sm">
          Launchpad · Resume AI Analyzer · 2026
        </div>
      </footer>
    </div>
    </AuthGate>
  )
}

export default App

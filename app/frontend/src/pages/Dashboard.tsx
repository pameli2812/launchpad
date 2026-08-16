import { useDashboard } from '@/hooks'
import { useAppStore } from '@/store'
import { Card } from '@/components/UI'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  BarChart, Bar,
} from 'recharts'
import {
  FileText, Target, BarChart3, TrendingUp, ArrowRight,
} from 'lucide-react'

const VERDICT_COLOR = {
  apply:      '#16a34a',
  borderline: '#d97706',
  skip:       '#dc2626',
}

export function DashboardPage() {
  const { data, isLoading, error } = useDashboard()
  const setCurrentTab = useAppStore((s) => s.setCurrentTab)

  if (isLoading) {
    return <div className="max-w-6xl mx-auto p-8 text-slate-500">Loading dashboard…</div>
  }
  if (error || !data) {
    return (
      <div className="max-w-6xl mx-auto p-8">
        <Card className="border-red-200 bg-red-50">
          <p className="text-red-700">Could not load dashboard: {(error as Error)?.message}</p>
        </Card>
      </div>
    )
  }

  // No data yet → show empty state with a nudge to the Analyze tab
  if (data.totals.analyses === 0) {
    return (
      <div className="max-w-6xl mx-auto p-8 space-y-6">
        <div className="border-b border-slate-200 pb-6">
          <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
        </div>
        <Card className="text-center py-16">
          <BarChart3 className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <p className="text-slate-700 font-semibold text-lg">No analyses yet</p>
          <p className="text-slate-400 text-sm mt-2 mb-5">
            Run your first JD analysis to start seeing trends, gap patterns and verdict
            breakdowns here.
          </p>
          <button
            onClick={() => setCurrentTab('analyze')}
            className="px-4 py-2 rounded-lg font-medium bg-blue-600 hover:bg-blue-700 text-white inline-flex items-center gap-2"
          >
            Go to Analyze <ArrowRight className="w-4 h-4" />
          </button>
        </Card>
      </div>
    )
  }

  const verdictPie = [
    { name: 'Apply',      value: data.verdicts.apply,      color: VERDICT_COLOR.apply },
    { name: 'Borderline', value: data.verdicts.borderline, color: VERDICT_COLOR.borderline },
    { name: 'Skip',       value: data.verdicts.skip,       color: VERDICT_COLOR.skip },
  ].filter((d) => d.value > 0)

  const timeline = data.timeline.map((t) => ({
    ...t,
    date: new Date(t.analyzed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
  }))

  return (
    <div className="max-w-6xl mx-auto p-8 space-y-6">
      <div className="border-b border-slate-200 pb-6">
        <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-slate-500 mt-1 text-sm">
          Click any chart to dive into the matching analyses.
        </p>
      </div>

      {/* ── Totals row ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile
          label="Resumes"
          value={data.totals.resumes}
          icon={FileText}
          onClick={() => setCurrentTab('setup')}
        />
        <StatTile
          label="Goal sets"
          value={data.totals.goal_sets}
          icon={Target}
          onClick={() => setCurrentTab('setup')}
        />
        <StatTile
          label="Analyses"
          value={data.totals.analyses}
          icon={BarChart3}
          onClick={() => setCurrentTab('history')}
        />
        <StatTile
          label="Avg fit score"
          value={data.totals.avg_fit !== null ? `${data.totals.avg_fit.toFixed(1)}/10` : '—'}
          icon={TrendingUp}
        />
      </div>

      {/* ── Verdict pie + Top resumes ────────────────────────────────────── */}
      <div className="grid lg:grid-cols-2 gap-4">
        <Card>
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Verdict distribution</h3>
          {verdictPie.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-12">No verdicts yet</p>
          ) : (
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={verdictPie}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={85}
                    innerRadius={50}
                    paddingAngle={2}
                    onClick={(_, idx) => {
                      // Clicking a slice → History tab (filter applied client-side).
                      setCurrentTab('history')
                      const verdict = verdictPie[idx]?.name?.toLowerCase()
                      if (verdict) {
                        sessionStorage.setItem('lp_history_filter', verdict)
                      }
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    {verdictPie.map((d, i) => (
                      <Cell key={i} fill={d.color} stroke="white" strokeWidth={2} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: any) => `${v ?? 0} analyses`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
          <VerdictLegend pie={verdictPie} setCurrentTab={setCurrentTab} />
        </Card>

        <Card>
          <h3 className="text-lg font-semibold text-slate-900 mb-4">Most-analyzed resumes</h3>
          {data.top_resumes.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-12">No data yet</p>
          ) : (
            <ul className="space-y-2">
              {data.top_resumes.map((r) => (
                <li
                  key={r.filename}
                  className="flex justify-between items-center px-3 py-2 rounded-lg hover:bg-slate-50 cursor-pointer"
                  onClick={() => setCurrentTab('history')}
                >
                  <span className="text-sm text-slate-700 truncate flex-1 mr-3" title={r.filename}>
                    {r.filename}
                  </span>
                  <span className="text-xs font-semibold bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                    {r.count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* ── Fit-score timeline ───────────────────────────────────────────── */}
      <Card>
        <h3 className="text-lg font-semibold text-slate-900 mb-4">
          Fit score over time
          <span className="text-slate-400 text-sm font-normal ml-2">
            (last {timeline.length} analyses)
          </span>
        </h3>
        {timeline.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-12">No analyses with scores yet</p>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeline} margin={{ top: 10, right: 20, bottom: 0, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 10]} ticks={[0, 2.5, 5, 7.5, 10]} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const p = payload[0].payload as typeof timeline[number]
                    return (
                      <div className="bg-white border border-slate-200 rounded-lg shadow-md p-3 text-xs">
                        <p className="font-semibold text-slate-900">
                          {p.jd_title || 'Untitled role'}
                          {p.company && <span className="text-slate-500"> @ {p.company}</span>}
                        </p>
                        <p className="text-slate-600 mt-0.5">
                          {p.date} · Fit {p.overall_fit.toFixed(1)}/10 · {p.verdict}
                        </p>
                      </div>
                    )
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="overall_fit"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={{ r: 4, fill: '#2563eb', strokeWidth: 0 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      {/* ── Top gap types ───────────────────────────────────────────────── */}
      <Card>
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Most common gap types</h3>
        {data.gap_types.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-12">No gaps recorded yet</p>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.gap_types} layout="vertical" margin={{ top: 5, right: 25, bottom: 5, left: 100 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                <XAxis type="number" stroke="#94a3b8" fontSize={11} />
                <YAxis dataKey="type" type="category" stroke="#94a3b8" fontSize={12} width={100} />
                <Tooltip formatter={(v: any) => `${v ?? 0} mentions`} />
                <Bar
                  dataKey="count"
                  fill="#3b82f6"
                  radius={[0, 4, 4, 0]}
                  cursor="pointer"
                  onClick={() => setCurrentTab('history')}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatTile({
  label, value, icon: Icon, onClick,
}: {
  label: string
  value: number | string
  icon: React.ComponentType<{ className?: string }>
  onClick?: () => void
}) {
  const clickable = !!onClick
  return (
    <Card
      className={clickable ? 'cursor-pointer hover:shadow-md hover:border-blue-200 transition-all' : ''}
      {...(onClick ? { onClick } as any : {})}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{label}</p>
          <p className="text-3xl font-bold text-slate-900 mt-1">{value}</p>
        </div>
        <Icon className="w-5 h-5 text-slate-300" />
      </div>
    </Card>
  )
}

function VerdictLegend({
  pie,
  setCurrentTab,
}: {
  pie: { name: string; value: number; color: string }[]
  setCurrentTab: (id: 'history') => void
}) {
  if (pie.length === 0) return null
  return (
    <div className="flex flex-wrap gap-2 justify-center mt-3">
      {pie.map((d) => (
        <button
          key={d.name}
          onClick={() => {
            setCurrentTab('history')
            sessionStorage.setItem('lp_history_filter', d.name.toLowerCase())
          }}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-50 hover:bg-slate-100 border border-slate-200"
        >
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.color }} />
          {d.name} · {d.value}
        </button>
      ))}
    </div>
  )
}

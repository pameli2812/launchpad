// ATS Rank UI Components - React

import { useState, useEffect } from 'react';
import apiClient from '@/api/client';

// ============================================================================
// 1. CircularScore Component - Main ATS Score Display
// ============================================================================

export const CircularScore = ({ score, grade, status }: { score: number; grade: string; status: string }) => {
  const circumference = 2 * Math.PI * 45;
  const progress = (score / 100) * circumference;
  const offset = circumference - progress;

  const getColor = () => {
    if (score >= 90) return '#10b981'; // Green
    if (score >= 80) return '#3b82f6'; // Blue
    if (score >= 70) return '#f59e0b'; // Amber
    if (score >= 60) return '#ef4444'; // Red
    return '#6b7280'; // Gray
  };

  return (
    <div className="flex flex-col items-center justify-center p-8">
      <div className="relative w-40 h-40">
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
          {/* Background circle */}
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="4"
          />
          {/* Progress circle */}
          <circle
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke={getColor()}
            strokeWidth="4"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-500"
          />
        </svg>
        {/* Score text */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <div className="text-4xl font-bold text-gray-900">{score}</div>
            <div className="text-sm text-gray-600">/100</div>
          </div>
        </div>
      </div>
      <div className="mt-6 text-center">
        <div className="text-2xl font-bold text-gray-900">{grade}</div>
        <div className="text-sm text-gray-600">{status}</div>
      </div>
    </div>
  );
};


// ============================================================================
// 2. ScoreBreakdown Component - Category-wise Scores
// ============================================================================

export const ScoreBreakdown = ({ breakdown }: { breakdown: Record<string, number> }) => {
  const categories = [
    { key: 'parsing', label: 'Parsing Compatibility', weight: '20%' },
    { key: 'structure', label: 'Resume Structure', weight: '15%' },
    { key: 'keywords', label: 'Keyword Coverage', weight: '20%' },
    { key: 'formatting', label: 'Formatting', weight: '10%' },
    { key: 'experience', label: 'Experience Quality', weight: '15%' },
    { key: 'skills', label: 'Skills Section', weight: '10%' },
    { key: 'action_verbs', label: 'Action Verbs', weight: '5%' },
    { key: 'contact', label: 'Contact Information', weight: '5%' },
  ];

  const getStatusColor = (score: number) => {
    if (score >= 90) return 'text-green-600';
    if (score >= 80) return 'text-blue-600';
    if (score >= 70) return 'text-amber-600';
    if (score >= 60) return 'text-orange-600';
    return 'text-red-600';
  };

  const getBarColor = (score: number) => {
    if (score >= 90) return 'bg-green-500';
    if (score >= 80) return 'bg-blue-500';
    if (score >= 70) return 'bg-amber-500';
    if (score >= 60) return 'bg-orange-500';
    return 'bg-red-500';
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-6">Score Breakdown</h2>
      <div className="space-y-4">
        {categories.map((category) => {
          const score = breakdown[category.key] || 0;
          return (
            <div key={category.key}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex-1">
                  <h3 className="text-sm font-medium text-gray-900">
                    {category.label}
                  </h3>
                  <p className="text-xs text-gray-500">Weight: {category.weight}</p>
                </div>
                <div className={`text-lg font-bold ${getStatusColor(score)}`}>
                  {score}
                </div>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all duration-500 ${getBarColor(score)}`}
                  style={{ width: `${score}%` }}
                ></div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};


// ============================================================================
// 3. RecommendationCard Component - Priority-based Recommendations
// ============================================================================

export const RecommendationCard = ({ level, message, detail }: { level: string; message: string; detail: string }) => {
  const getLevelStyles = () => {
    switch (level) {
      case 'critical':
        return 'bg-red-50 border-l-4 border-red-400 text-red-700';
      case 'high':
        return 'bg-orange-50 border-l-4 border-orange-400 text-orange-700';
      case 'medium':
        return 'bg-amber-50 border-l-4 border-amber-400 text-amber-700';
      case 'low':
        return 'bg-blue-50 border-l-4 border-blue-400 text-blue-700';
      default:
        return 'bg-gray-50 border-l-4 border-gray-400 text-gray-700';
    }
  };

  const getIcon = () => {
    switch (level) {
      case 'critical':
        return '❌';
      case 'high':
        return '⚠️';
      case 'medium':
        return '⚙️';
      case 'low':
        return 'ℹ️';
      default:
        return '•';
    }
  };

  return (
    <div className={`p-4 rounded ${getLevelStyles()}`}>
      <div className="flex items-start">
        <span className="mr-3">{getIcon()}</span>
        <div className="flex-1">
          <h4 className="font-semibold text-sm mb-1">{message}</h4>
          <p className="text-xs opacity-90">{detail}</p>
        </div>
      </div>
    </div>
  );
};


// ============================================================================
// 4. RecommendationsPanel Component - All Recommendations
// ============================================================================

export const RecommendationsPanel = ({ recommendations }: { recommendations: Record<string, Array<{ message: string; detail: string }>> }) => {
  const [expandedLevel, setExpandedLevel] = useState<string | null>(null);

  const levels = [
    { key: 'critical', label: '🚨 Critical', color: 'text-red-600' },
    { key: 'high', label: '⚠️ High Priority', color: 'text-orange-600' },
    { key: 'medium', label: '⚙️ Medium', color: 'text-amber-600' },
    { key: 'low', label: 'ℹ️ Low', color: 'text-blue-600' },
  ];

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-6">Improvement Suggestions</h2>
      <div className="space-y-3">
        {levels.map((level) => {
          const recs = recommendations[level.key] || [];
          const count = recs.length;

          return (
            <div key={level.key}>
              <button
                onClick={() =>
                  setExpandedLevel(
                    expandedLevel === level.key ? null : level.key
                  )
                }
                className="flex items-center justify-between w-full p-3 bg-gray-50 hover:bg-gray-100 rounded transition"
              >
                <span className={`font-semibold ${level.color}`}>
                  {level.label} ({count})
                </span>
                <span className="text-gray-500">
                  {expandedLevel === level.key ? '▼' : '▶'}
                </span>
              </button>

              {expandedLevel === level.key && count > 0 && (
                <div className="mt-2 space-y-2 pl-3 border-l-2 border-gray-200">
                  {recs.map((rec, idx) => (
                    <RecommendationCard
                      key={idx}
                      level={level.key}
                      message={rec.message}
                      detail={rec.detail}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};


// ============================================================================
// 5. CompatibilityTable Component - ATS Platform Scores
// ============================================================================

export const CompatibilityTable = ({ compatibility }: { compatibility: Record<string, number> }) => {
  const platforms = [
    { key: 'greenhouse', label: 'Greenhouse' },
    { key: 'lever', label: 'Lever' },
    { key: 'workday', label: 'Workday' },
    { key: 'taleo', label: 'Oracle Taleo' },
    { key: 'icims', label: 'iCIMS' },
    { key: 'smartrecruiters', label: 'SmartRecruiters' },
  ];

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-6">ATS Compatibility</h2>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-2 px-3 font-semibold text-gray-900">Platform</th>
              <th className="text-center py-2 px-3 font-semibold text-gray-900">Score</th>
            </tr>
          </thead>
          <tbody>
            {platforms.map((platform) => {
              const score = compatibility[platform.key] || 0;
              const getColor = () => {
                if (score >= 90) return 'bg-green-100 text-green-900';
                if (score >= 80) return 'bg-blue-100 text-blue-900';
                if (score >= 70) return 'bg-amber-100 text-amber-900';
                return 'bg-red-100 text-red-900';
              };

              return (
                <tr key={platform.key} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-3 px-3 text-gray-900">{platform.label}</td>
                  <td className="py-3 px-3 text-center">
                    <span
                      className={`inline-block px-3 py-1 rounded font-semibold text-sm ${getColor()}`}
                    >
                      {score}%
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};


// ============================================================================
// 6. Main ATSRank Component - Full Page
// ============================================================================

interface ATSReport {
  overall_score: number;
  grade: string;
  status: string;
  summary: string;
  breakdown: Record<string, number>;
  critical_issues: string[];
  all_recommendations: Record<string, Array<{ message: string; detail: string }>>;
  ats_compatibility: Record<string, number>;
}

export const ATSRank = ({ resumeId }: { resumeId: string }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ATSReport | null>(null);
  const [selectedRole, setSelectedRole] = useState('full_stack_engineer');

  const roles = [
    { id: 'backend_engineer', label: 'Backend Engineer' },
    { id: 'frontend_engineer', label: 'Frontend Engineer' },
    { id: 'full_stack_engineer', label: 'Full Stack Engineer' },
    { id: 'data_engineer', label: 'Data Engineer' },
    { id: 'devops_engineer', label: 'DevOps Engineer' },
    { id: 'ai_ml_engineer', label: 'AI/ML Engineer' },
  ];

  const analyzeResume = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.post(
        '/ats/analyze',
        {
          resume_id: resumeId,
          role: selectedRole,
        }
      );

      setReport(response.data);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Failed to analyze resume';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    analyzeResume();
  }, [selectedRole, resumeId]);

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
        Error: {error}
      </div>
    );
  }

  return (
    <div className="w-full max-w-6xl mx-auto py-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">ATS Rank</h1>
        <p className="text-gray-600">
          See how your resume will be parsed by Applicant Tracking Systems
        </p>
      </div>

      {/* Role Selector */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-900 mb-2">
          Target Job Role
        </label>
        <select
          value={selectedRole}
          onChange={(e) => setSelectedRole(e.target.value)}
          className="w-full max-w-sm px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {roles.map((role) => (
            <option key={role.id} value={role.id}>
              {role.label}
            </option>
          ))}
        </select>
      </div>

      {/* Main Score Card */}
      {report && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <div className="lg:col-span-1">
              <div className="bg-white rounded-lg shadow">
                <CircularScore
                  score={report.overall_score}
                  grade={report.grade}
                  status={report.status}
                />
              </div>
            </div>

            <div className="lg:col-span-2">
              <div className="bg-white rounded-lg shadow p-6 h-full">
                <h2 className="text-lg font-bold text-gray-900 mb-4">Summary</h2>
                <p className="text-gray-700 leading-relaxed">{report.summary}</p>

                {report.critical_issues.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <h3 className="font-semibold text-red-700 mb-2">
                      Critical Issues:
                    </h3>
                    <ul className="list-disc list-inside space-y-1">
                      {report.critical_issues.map((issue, idx) => (
                        <li key={idx} className="text-sm text-red-600">
                          {issue}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Score Breakdown */}
          <div className="mb-8">
            <ScoreBreakdown breakdown={report.breakdown} />
          </div>

          {/* Recommendations */}
          <div className="mb-8">
            <RecommendationsPanel recommendations={report.all_recommendations} />
          </div>

          {/* Compatibility Table */}
          <div className="mb-8">
            <CompatibilityTable compatibility={report.ats_compatibility} />
          </div>

          {/* Download Report Button */}
          <div className="text-center">
            <button
              onClick={() => window.print()}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            >
              📥 Download Report
            </button>
          </div>
        </>
      )}

      {loading && (
        <div className="text-center py-12">
          <div className="inline-block animate-spin">⚙️</div>
          <p className="mt-2 text-gray-600">Analyzing your resume...</p>
        </div>
      )}
    </div>
  );
};

export default ATSRank;
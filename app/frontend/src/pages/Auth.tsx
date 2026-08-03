import { useState, useEffect } from 'react'

// ── Types ─────────────────────────────────────────────────────────────────────

type AuthView = 'login' | 'signup' | 'forgot' | 'reset' | 'check-email'

type User = {
  id: string
  email: string
  full_name: string
  avatar_url?: string
  is_verified: boolean
}

// ── API helpers ───────────────────────────────────────────────────────────────

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

async function apiPost(path: string, body: object) {
  const token = localStorage.getItem('lp_access_token')
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: 'include',   // send httpOnly refresh cookie
    body: JSON.stringify(body),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? 'Request failed')
  return data
}

// ── Auth context (simple module-level state for this app) ─────────────────────

let _user: User | null = null
let _listeners: Array<() => void> = []

export function getUser() { return _user }

export function setUser(u: User | null) {
  _user = u
  if (u) localStorage.setItem('lp_user', JSON.stringify(u))
  else    localStorage.removeItem('lp_user')
  _listeners.forEach(l => l())
}

export function useUser(): User | null {
  const [, rerender] = useState(0)
  useEffect(() => {
    const cb = () => rerender(n => n + 1)
    _listeners.push(cb)
    return () => { _listeners = _listeners.filter(l => l !== cb) }
  }, [])
  return _user
}

// Restore user from localStorage on page load
try {
  const stored = localStorage.getItem('lp_user')
  if (stored) _user = JSON.parse(stored)
} catch {}

// ── Logo ──────────────────────────────────────────────────────────────────────

function Logo() {
  return (
    <svg width="140" height="28" viewBox="0 0 182 36" fill="none">
      <polygon points="18,2 28,8 28,24 18,30 8,24 8,8" fill="#2563eb"/>
      <polygon points="18,2 28,8 28,24 18,30 8,24 8,8" fill="none" stroke="#1d4ed8" strokeWidth="0.75"/>
      <rect x="14.5" y="13" width="7" height="10" rx="3.5" fill="white"/>
      <path d="M14.5,16 Q14.5,8 18,6 Q21.5,8 21.5,16 Z" fill="white"/>
      <circle cx="18" cy="16.5" r="2.2" fill="#bfdbfe"/>
      <circle cx="18" cy="16.5" r="1.3" fill="#2563eb"/>
      <path d="M14.5,19.5 L10.5,24 L14.5,22.5 Z" fill="#93c5fd"/>
      <path d="M21.5,19.5 L25.5,24 L21.5,22.5 Z" fill="#93c5fd"/>
      <ellipse cx="18" cy="27" rx="2.2" ry="3" fill="#fbbf24"/>
      <ellipse cx="18" cy="28.5" rx="1.2" ry="2" fill="#f97316"/>
      <text x="36" y="24" fontFamily="system-ui,-apple-system,sans-serif" fontSize="22" fontWeight="700" letterSpacing="-0.5">
        <tspan fill="#0f172a">Launch</tspan><tspan fill="#2563eb">pad</tspan>
      </text>
    </svg>
  )
}

// ── Google button (disabled) ──────────────────────────────────────────────────

function GoogleButton({ label }: { label: string }) {
  return (
    <button
      type="button"
      disabled
      title="Google sign-in coming soon"
      className="w-full flex items-center justify-center gap-3 px-4 py-2.5 border border-slate-200 rounded-xl bg-slate-50 text-slate-400 font-medium text-sm cursor-not-allowed"
    >
      <svg width="18" height="18" viewBox="0 0 18 18" className="opacity-40">
        <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
        <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
        <path fill="#FBBC05" d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332z"/>
        <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58z"/>
      </svg>
      {label} (coming soon)
    </button>
  )
}

// ── Input ─────────────────────────────────────────────────────────────────────

function Field({
  label, type = 'text', value, onChange, placeholder, error,
}: {
  label: string; type?: string; value: string
  onChange: (v: string) => void; placeholder?: string; error?: string
}) {
  const [show, setShow] = useState(false)
  const isPassword = type === 'password'
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
      <div className="relative">
        <input
          type={isPassword && show ? 'text' : type}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          className={`w-full px-4 py-2.5 border rounded-xl text-sm outline-none transition-all
            ${error ? 'border-red-400 focus:ring-2 focus:ring-red-200' : 'border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100'}`}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShow(s => !s)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs"
          >
            {show ? 'Hide' : 'Show'}
          </button>
        )}
      </div>
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  )
}

// ── Divider ───────────────────────────────────────────────────────────────────

function Divider() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-px bg-slate-200" />
      <span className="text-xs text-slate-400 font-medium">or</span>
      <div className="flex-1 h-px bg-slate-200" />
    </div>
  )
}

// ── Auth card shell ───────────────────────────────────────────────────────────

function AuthCard({ children, title, subtitle }: { children: React.ReactNode; title: string; subtitle?: string }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-8">
          <Logo />
        </div>
        <div className="bg-white rounded-2xl shadow-lg border border-slate-100 p-8 space-y-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
            {subtitle && <p className="text-slate-500 text-sm mt-1">{subtitle}</p>}
          </div>
          {children}
        </div>
      </div>
    </div>
  )
}

// ── Login view ────────────────────────────────────────────────────────────────

function LoginView({ onSwitch }: { onSwitch: (v: AuthView) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await apiPost('/auth/login', { email, password })
      localStorage.setItem('lp_access_token', data.access_token)
      setUser(data.user)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthCard title="Welcome back" subtitle="Sign in to your Launchpad account">
      <GoogleButton label="Continue with Google" />
      <Divider />
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@example.com" />
        <div>
          <Field label="Password" type="password" value={password} onChange={setPassword} placeholder="••••••••" />
          <button
            type="button"
            onClick={() => onSwitch('forgot')}
            className="text-xs text-blue-600 hover:underline mt-1 float-right"
          >
            Forgot password?
          </button>
        </div>
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-2.5">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold rounded-xl transition-all text-sm shadow-sm"
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p className="text-center text-sm text-slate-500">
        Don't have an account?{' '}
        <button onClick={() => onSwitch('signup')} className="text-blue-600 font-semibold hover:underline">
          Sign up free
        </button>
      </p>
    </AuthCard>
  )
}

// ── Sign up view ──────────────────────────────────────────────────────────────

function SignUpView({ onSwitch }: { onSwitch: (v: AuthView) => void }) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)

  const validate = () => {
    const e: Record<string, string> = {}
    if (!fullName.trim()) e.fullName = 'Full name is required'
    if (!email.includes('@')) e.email = 'Enter a valid email'
    if (password.length < 8) e.password = 'Password must be at least 8 characters'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return
    setLoading(true)
    try {
      const data = await apiPost('/auth/signup', { email, full_name: fullName, password })
      localStorage.setItem('lp_access_token', data.access_token)
      setUser(data.user)
    } catch (err: any) {
      setErrors({ form: err.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthCard title="Create your account" subtitle="Start analysing resumes in minutes">
      <GoogleButton label="Sign up with Google" />
      <Divider />
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Full name" value={fullName} onChange={setFullName} placeholder="Jane Smith" error={errors.fullName} />
        <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@example.com" error={errors.email} />
        <Field label="Password" type="password" value={password} onChange={setPassword} placeholder="Min. 8 characters" error={errors.password} />
        {errors.form && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-2.5">
            {errors.form}
          </div>
        )}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold rounded-xl transition-all text-sm shadow-sm"
        >
          {loading ? 'Creating account…' : 'Create account'}
        </button>
      </form>
      <p className="text-center text-sm text-slate-500">
        Already have an account?{' '}
        <button onClick={() => onSwitch('login')} className="text-blue-600 font-semibold hover:underline">
          Sign in
        </button>
      </p>
    </AuthCard>
  )
}

// ── Forgot password view ──────────────────────────────────────────────────────

function ForgotView({ onSwitch }: { onSwitch: (v: AuthView) => void }) {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [resetToken, setResetToken] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await apiPost('/auth/forgot-password', { email })
      // ✅ Now returns reset_token directly in response (local dev)
      if (data.reset_token) {
        setResetToken(data.reset_token)
        // Auto-redirect to reset password with token
        setTimeout(() => {
          window.location.href = `/reset-password?token=${data.reset_token}`
        }, 500)
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Show success message while redirecting
  if (resetToken) {
    return (
      <AuthCard title="Password reset link ready!" subtitle="Redirecting to reset page...">
        <div className="bg-green-50 border border-green-200 text-green-800 text-sm rounded-xl px-4 py-4 text-center space-y-3">
          <p>✅ Reset link generated successfully!</p>
          <p className="text-xs text-green-700">
            Redirecting to password reset page... If not redirected in 2 seconds, <a href={`/reset-password?token=${resetToken}`} className="font-semibold underline">click here</a>.
          </p>
        </div>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Reset your password" subtitle="Enter your email and we'll send a reset link">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Email" type="email" value={email} onChange={setEmail} placeholder="you@example.com" />
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-2.5">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={loading || !email.includes('@')}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold rounded-xl transition-all text-sm shadow-sm"
        >
          {loading ? 'Generating reset link…' : 'Send reset link'}
        </button>
      </form>
      <button
        onClick={() => onSwitch('login')}
        className="w-full text-center text-sm text-slate-500 hover:text-slate-700"
      >
        ← Back to sign in
      </button>
    </AuthCard>
  )
}

// ── Reset password view ───────────────────────────────────────────────────────

function ResetView({ token, onSwitch }: { token: string; onSwitch: (v: AuthView) => void }) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (password !== confirm) { setError('Passwords do not match'); return }
    if (password.length < 8)  { setError('Password must be at least 8 characters'); return }
    setLoading(true)
    setError('')
    try {
      await apiPost('/auth/reset-password', { token, new_password: password })
      setDone(true)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <AuthCard title="Password updated!" subtitle="You can now sign in with your new password">
        <button
          onClick={() => onSwitch('login')}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl text-sm"
        >
          Sign in
        </button>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Set new password" subtitle="Choose a strong password for your account">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="New password" type="password" value={password} onChange={setPassword} placeholder="Min. 8 characters" />
        <Field label="Confirm password" type="password" value={confirm} onChange={setConfirm} placeholder="Repeat password" />
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-2.5">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold rounded-xl text-sm"
        >
          {loading ? 'Updating…' : 'Update password'}
        </button>
      </form>
    </AuthCard>
  )
}

// ── AuthGate — wraps the whole app ────────────────────────────────────────────

export function AuthGate({ children }: { children: React.ReactNode }) {
  const user = useUser()
  const [view, setView] = useState<AuthView>('login')

  // Detect ?token= from password reset link
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('token')) setView('reset')
  }, [])

  const resetToken = new URLSearchParams(window.location.search).get('token') ?? ''

  if (!user) {
    if (view === 'signup') return <SignUpView  onSwitch={setView} />
    if (view === 'forgot') return <ForgotView  onSwitch={setView} />
    if (view === 'reset')  return <ResetView   token={resetToken} onSwitch={setView} />
    return <LoginView onSwitch={setView} />
  }

  return <>{children}</>
}

// ── UserMenu — shown in the header when logged in ─────────────────────────────

export function UserMenu() {
  const user = useUser()
  const [open, setOpen] = useState(false)

  if (!user) return null

  const handleLogout = async () => {
    try { await apiPost('/auth/logout', {}) } catch {}
    localStorage.removeItem('lp_access_token')
    localStorage.removeItem('lp_user')
    setUser(null)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-xl hover:bg-slate-100 transition-colors"
      >
        {user.avatar_url ? (
          <img src={user.avatar_url} className="w-7 h-7 rounded-full object-cover" alt={user.full_name} />
        ) : (
          <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
            {user.full_name?.[0]?.toUpperCase() ?? user.email[0].toUpperCase()}
          </div>
        )}
        <span className="text-sm font-medium text-slate-700">{user.full_name || user.email}</span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-slate-400">
          <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-2 w-56 bg-white rounded-xl shadow-lg border border-slate-100 z-40 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100">
              <p className="text-sm font-semibold text-slate-900 truncate">{user.full_name}</p>
              <p className="text-xs text-slate-500 truncate">{user.email}</p>
            </div>
            <button
              onClick={handleLogout}
              className="w-full text-left px-4 py-3 text-sm text-red-600 hover:bg-red-50 transition-colors font-medium"
            >
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  )
}
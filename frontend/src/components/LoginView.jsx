import { useState } from 'react'
import {
  Lock,
  User,
  SignIn,
  ShieldCheck,
  Waveform,
  CheckCircle,
  Key,
  Lightning,
} from '@phosphor-icons/react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const defaultApiBaseUrl =
  typeof window !== 'undefined' && ['localhost', '127.0.0.1'].includes(window.location.hostname)
    ? 'http://localhost:8000'
    : 'https://voice-ai-agent-ybml.onrender.com'
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl

export function LoginView({ onLoginSuccess }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin123')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleLogin = async (e) => {
    e?.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await fetch(`${apiBaseUrl}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password: password.trim() }),
      })

      if (!response.ok) {
        const text = await response.text()
        throw new Error(text || 'Invalid username or password')
      }

      const data = await response.json()
      if (data.access_token) {
        window.localStorage?.setItem('voice_ai_admin_token', data.access_token)
        window.localStorage?.setItem('voice_ai_username', data.user?.username || username.trim())
        if (onLoginSuccess) {
          onLoginSuccess(data)
        } else {
          window.location.href = '/overview'
        }
      } else {
        throw new Error('No access token received from authentication server')
      }
    } catch (err) {
      console.error('Login error:', err)
      setError(err.message || 'Login failed. Please verify credentials.')
    } finally {
      setLoading(false)
    }
  }

  const fillQuickDemo = (user, pass) => {
    setUsername(user)
    setPassword(pass)
    setError('')
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 bg-gradient-to-br from-background via-muted/30 to-background relative overflow-hidden">
      {/* Decorative backdrop glow elements */}
      <div className="absolute top-1/4 left-1/4 -translate-x-1/2 -translate-y-1/2 size-96 rounded-full bg-primary/10 blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 translate-x-1/2 translate-y-1/2 size-96 rounded-full bg-emerald-500/10 blur-3xl pointer-events-none" />

      <div className="w-full max-w-md relative z-10 space-y-6">
        {/* Brand header */}
        <div className="text-center space-y-2">
          <div className="inline-flex size-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-primary/20 mb-2">
            <Waveform className="size-8" weight="duotone" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Voice AI Enterprise</h1>
          <p className="text-xs text-muted-foreground max-w-xs mx-auto">
            Autonomous multi-agent voice orchestration, secured telephony readiness, and graph memory
          </p>
        </div>

        {/* Login Card */}
        <Card className="border-border/60 shadow-xl backdrop-blur-md bg-card/90">
          <CardHeader className="space-y-1 pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg font-semibold">Sign in to Console</CardTitle>
              <Badge variant="outline" className="text-xs font-normal border-primary/30 text-primary">
                Role-Based JWT
              </Badge>
            </div>
            <CardDescription className="text-xs">
              Enter your administrative credentials to access agent configurations and memory.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive flex items-start gap-2">
                <span className="font-semibold shrink-0">Error:</span>
                <span className="break-words">{error}</span>
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-3.5">
              <div className="space-y-1.5">
                <Label htmlFor="login-username" className="text-xs font-medium flex items-center gap-1.5">
                  <User className="size-3.5 text-muted-foreground" />
                  Login ID / Username
                </Label>
                <Input
                  id="login-username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  required
                  className="h-10 text-sm"
                  autoComplete="username"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor="login-password" className="text-xs font-medium flex items-center gap-1.5">
                    <Lock className="size-3.5 text-muted-foreground" />
                    Password
                  </Label>
                </div>
                <Input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="h-10 text-sm"
                  autoComplete="current-password"
                />
              </div>

              <Button
                type="submit"
                className="w-full h-10 gap-2 font-medium shadow-md shadow-primary/20"
                disabled={loading || !password.trim()}
              >
                {loading ? (
                  <>
                    <span className="size-4 rounded-full border-2 border-primary-foreground border-t-transparent animate-spin" />
                    Verifying token...
                  </>
                ) : (
                  <>
                    <SignIn className="size-4" weight="bold" />
                    Sign In to Dashboard
                  </>
                )}
              </Button>
            </form>

            {/* Quick credentials hint */}
            <div className="pt-2 border-t text-xs text-muted-foreground space-y-2">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1 font-medium text-foreground/80">
                  <Key className="size-3 text-primary" weight="duotone" />
                  Default credentials:
                </span>
                <button
                  type="button"
                  onClick={() => fillQuickDemo('admin', 'admin123')}
                  className="text-xs text-primary hover:underline font-medium"
                >
                  Autofill admin
                </button>
              </div>
              <div className="p-2 rounded-md bg-muted/40 font-mono text-[11px] flex justify-between items-center">
                <span>Login ID: <strong>admin</strong></span>
                <span>Password: <strong>admin123</strong></span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Interview security highlights note */}
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-3 text-xs space-y-1.5">
          <div className="flex items-center gap-1.5 font-semibold text-foreground">
            <ShieldCheck className="size-4 text-emerald-500" weight="duotone" />
            Security & Data Privacy Architecture
          </div>
          <p className="text-muted-foreground text-[11px] leading-relaxed">
            Authenticated via HMAC-SHA256 JWT tokens with constant-time password hash verification. Multi-tenant isolation and per-agent memory scoping ensure private data isolation and strict PII redacting.
          </p>
        </div>
      </div>
    </div>
  )
}

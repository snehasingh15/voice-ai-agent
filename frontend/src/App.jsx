import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useResilientWebSocket } from '@/hooks/use-resilient-websocket'
import {
  ChatCircle,
  PaperPlaneTilt,
  PhoneCall,
  Pulse,
  UploadSimple,
  Waveform,
  Plus,
  Sparkle,
  CheckCircle,
  Eye,
  Trash,
  Robot,
  ArrowsClockwise,
  Check,
  FileText,
} from '@phosphor-icons/react'
import { Orb } from '@/components/ui/orb'

import { AppShell } from '@/components/app-shell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'https://voice-ai-agent-ybml.onrender.com'
const wsUrl = `${apiBaseUrl.replace(/^http/, 'ws')}/ws/session`


function authHeaders(extra = {}) {
  const token = window.localStorage?.getItem('voice_ai_admin_token')
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

async function adminFetch(path, options = {}) {
  const request = () => fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: authHeaders(options.headers || {}),
  })

  let response = await request()
  if (response.status !== 401) return response

  window.localStorage?.removeItem('voice_ai_admin_token')
  const password = window.prompt('Admin password')
  if (!password) return response

  const login = await fetch(`${apiBaseUrl}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  })
  if (!login.ok) return login

  const data = await login.json()
  if (data.access_token) window.localStorage?.setItem('voice_ai_admin_token', data.access_token)
  response = await request()
  return response
}
async function getJson(path) {
  const response = await fetch(`${apiBaseUrl}${path}`)
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json()
}

function formatMs(value) {
  return value === null || value === undefined ? '—' : `${Math.round(value)} ms`
}

function formatTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

function sentimentVariant(sentiment) {
  if (sentiment === 'positive') return 'success'
  if (sentiment === 'negative') return 'destructive'
  return 'secondary'
}

function MetricCard({ label, value }) {
  return (
    <Card className="gap-1 py-4">
      <CardHeader className="px-4">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-3xl font-semibold tabular-nums">{value}</CardTitle>
      </CardHeader>
    </Card>
  )
}

function PageIntro({ title, lede, meta }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex max-w-2xl flex-col gap-2">
        <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        <p className="text-muted-foreground text-sm">{lede}</p>
      </div>
      <Badge variant="outline" className="w-fit shrink-0">
        {meta}
      </Badge>
    </div>
  )
}

function Overview() {
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: () => getJson('/api/analytics/summary'),
  })

  const seedDemo = useMutation({
    mutationFn: async () => {
      const res = await adminFetch('/api/admin/seed-demo-data', { method: 'POST' })
      if (!res.ok) throw new Error(await res.text())
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analytics-summary'] })
      queryClient.invalidateQueries({ queryKey: ['recent-interactions'] })
      queryClient.invalidateQueries({ queryKey: ['bookings'] })
      queryClient.invalidateQueries({ queryKey: ['handoffs'] })
      queryClient.invalidateQueries({ queryKey: ['token-metrics'] })
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      queryClient.invalidateQueries({ queryKey: ['doctors'] })
    },
  })

  const sentiment = data?.sentiment_breakdown ?? {}
  const sentimentRows = [
    ['Positive', sentiment.positive || 0],
    ['Neutral', sentiment.neutral || 0],
    ['Negative', sentiment.negative || 0],
  ]
  const maxSentiment = Math.max(1, ...sentimentRows.map(([, value]) => value))

  return (
    <AppShell title="Overview">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex max-w-2xl flex-col gap-2">
          <h2 className="text-2xl font-semibold tracking-tight">Voice agent performance at a glance</h2>
          <p className="text-muted-foreground text-sm">
            Inspect live latency, sentiment, and call volume from the backend to decide where to focus next.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => seedDemo.mutate()}
            disabled={seedDemo.isPending}
            className="gap-1.5"
          >
            <Sparkle size={16} weight="duotone" className="text-primary" />
            {seedDemo.isPending ? 'Seeding demo data…' : 'Seed Demo Data'}
          </Button>
          <Badge variant="outline" className="w-fit shrink-0">
            {isLoading ? 'Loading' : error ? 'API unavailable' : 'Live data'}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <MetricCard label="Average STT latency" value={formatMs(data?.avg_stt_latency_ms)} />
        <MetricCard label="Average LLM latency" value={formatMs(data?.avg_llm_latency_ms)} />
        <MetricCard label="Average TTS latency" value={formatMs(data?.avg_tts_latency_ms)} />
        <MetricCard label="Total calls" value={data?.total_calls ?? '—'} />
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-7">
          <CardHeader>
            <CardTitle>Sentiment distribution</CardTitle>
            <CardDescription>Bars share one scale and reflect the counts from the analytics summary.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-4">
              {sentimentRows.map(([label, value]) => (
                <div key={label} className="grid grid-cols-[80px_1fr_36px] items-center gap-3">
                  <span className="text-sm font-medium">{label}</span>
                  <div className="h-2.5 overflow-hidden rounded-full border bg-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${(value / maxSentiment) * 100}%` }}
                    />
                  </div>
                  <strong className="text-right text-sm tabular-nums">{value}</strong>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-muted/40 lg:col-span-5">
          <CardHeader>
            <Pulse className="size-6 text-primary" weight="duotone" />
            <CardTitle>What to check first</CardTitle>
            <CardDescription>
              Latency metrics are the quickest signal for user experience. Recent interactions preserve the audit
              trail for caller, tool, and response behavior.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    </AppShell>
  )
}

function Interactions() {
  const { data = [], isLoading, error } = useQuery({
    queryKey: ['recent-interactions'],
    queryFn: () => getJson('/api/analytics/recent'),
  })

  return (
    <AppShell title="Interactions">
      <PageIntro
        title="Recent calls keep latency, sentiment, and tool use auditable"
        lede="Each row reflects one backend interaction, ordered by the API response."
        meta={isLoading ? 'Loading' : error ? 'API unavailable' : `${data.length} rows`}
      />
      <Card>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Caller</TableHead>
                <TableHead>Sentiment</TableHead>
                <TableHead>Tool</TableHead>
                <TableHead className="text-right">STT</TableHead>
                <TableHead className="text-right">LLM</TableHead>
                <TableHead className="text-right">TTS</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.length ? (
                data.map((row) => (
                  <TableRow key={`${row.timestamp}-${row.caller_id}`}>
                    <TableCell className="text-muted-foreground">{formatTime(row.timestamp)}</TableCell>
                    <TableCell>{row.caller_id || 'anonymous'}</TableCell>
                    <TableCell>
                      <Badge variant={sentimentVariant(row.sentiment)}>{row.sentiment || 'neutral'}</Badge>
                    </TableCell>
                    <TableCell>{row.tool_used || 'none'}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatMs(row.stt_latency_ms)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatMs(row.llm_latency_ms)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatMs(row.tts_latency_ms)}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={7} className="text-muted-foreground text-center">
                    No records returned.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </AppShell>
  )
}

function Bookings() {
  const { data = [], isLoading, error } = useQuery({
    queryKey: ['bookings'],
    queryFn: () => getJson('/api/bookings'),
  })

  return (
    <AppShell title="Bookings">
      <PageIntro
        title="Tool calls connect caller intent to the agent response"
        lede="This view keeps bookings and tool activity readable without hiding transcript or reply context."
        meta={isLoading ? 'Loading' : error ? 'API unavailable' : `${data.length} rows`}
      />
      <Card>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Created</TableHead>
                <TableHead>Patient</TableHead>
                <TableHead>Doctor / Department</TableHead>
                <TableHead>Date & time</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.length ? (
                data.map((row) => (
                  <TableRow key={row._id || `${row.createdAt}-${row.patient_name}`}>
                    <TableCell className="text-muted-foreground">{formatTime(row.createdAt)}</TableCell>
                    <TableCell>{row.patient_name || row.caller_id || 'anonymous'}</TableCell>
                    <TableCell>{row.doctorName || row.department || '—'}</TableCell>
                    <TableCell>{row.appointment_date || '—'} {row.appointment_time || ''}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{row.status || 'requested'}</Badge>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={5} className="text-muted-foreground text-center">
                    No records returned.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </AppShell>
  )
}

function getStatusBadgeStyle(status) {
  switch (status?.toLowerCase()) {
    case 'confirmed':
      return 'bg-emerald-500/15 text-emerald-600 border-emerald-500/30 dark:text-emerald-400 dark:bg-emerald-950/40'
    case 'completed':
      return 'bg-blue-500/15 text-blue-600 border-blue-500/30 dark:text-blue-400 dark:bg-blue-950/40'
    case 'cancelled':
      return 'bg-rose-500/15 text-rose-600 border-rose-500/30 dark:text-rose-400 dark:bg-rose-950/40'
    case 'pending':
    case 'requested':
    default:
      return 'bg-amber-500/15 text-amber-600 border-amber-500/30 dark:text-amber-400 dark:bg-amber-950/40'
  }
}

function CalendarView() {
  const queryClient = useQueryClient()
  const { data = { bookings: [], doctors: [] }, isLoading, error, refetch } = useQuery({
    queryKey: ['calendar'],
    queryFn: () => getJson('/api/calendar'),
  })

  const updateStatus = useMutation({
    mutationFn: async ({ id, status }) => {
      const response = await fetch(`${apiBaseUrl}/api/bookings/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      if (!response.ok) throw new Error(await response.text())
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
      queryClient.invalidateQueries({ queryKey: ['bookings'] })
    },
  })

  return (
    <AppShell title="Calendar">
      <PageIntro
        title="Appointment calendar and conflict view"
        lede="Inspect real bookings by doctor, date, slot, and live status."
        meta={isLoading ? 'Loading' : error ? 'API unavailable' : `${data.bookings.length} bookings`}
      />
      <Card>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Time</TableHead>
                <TableHead>Doctor / Service</TableHead>
                <TableHead>Patient / Concern</TableHead>
                <TableHead>Status (Change Directly)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.bookings.length ? (
                data.bookings.map((row) => (
                  <TableRow key={row._id}>
                    <TableCell className="font-mono text-xs">{row.appointment_date || '—'}</TableCell>
                    <TableCell className="font-mono text-xs font-semibold">{row.appointment_time || '—'}</TableCell>
                    <TableCell className="font-medium">{row.doctor_name || row.doctorName || row.department || '—'}</TableCell>
                    <TableCell>{row.patient_name || row.caller_id || '—'}</TableCell>
                    <TableCell>
                      <div className="relative inline-block w-36">
                        <select
                          value={row.status || 'pending'}
                          onChange={(e) => updateStatus.mutate({ id: row._id, status: e.target.value })}
                          disabled={updateStatus.isPending}
                          className={`w-full appearance-none rounded-lg border px-3 py-1.5 text-xs font-semibold tracking-wide cursor-pointer focus:outline-hidden focus:ring-2 focus:ring-primary/40 transition-all ${getStatusBadgeStyle(
                            row.status
                          )}`}
                        >
                          <option value="pending" className="bg-background text-foreground">● Pending</option>
                          <option value="confirmed" className="bg-background text-foreground">● Confirmed</option>
                          <option value="completed" className="bg-background text-foreground">● Completed</option>
                          <option value="cancelled" className="bg-background text-foreground">● Cancelled</option>
                        </select>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-6 text-muted-foreground">
                    No bookings found in calendar.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </AppShell>
  )
}

function RagInspector() {
  const [query, setQuery] = useState('doctor timings')
  const [result, setResult] = useState(null)
  const inspect = useMutation({
    mutationFn: async (searchQuery) => {
      const q = searchQuery !== undefined ? searchQuery : query
      const response = await fetch(`${apiBaseUrl}/api/rag/inspect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      })
      if (!response.ok) throw new Error(await response.text())
      return response.json()
    },
    onSuccess: setResult,
  })

  const quickQueries = [
    'doctor timings',
    'broadband plans',
    'red PON light',
    'appointment policy',
    'clinic hours',
    'billing cycle',
  ]

  const handleQuickSearch = (q) => {
    setQuery(q)
    inspect.mutate(q)
  }

  return (
    <AppShell title="RAG Inspector">
      <PageIntro
        title="RAG Knowledge Grounding & Transparency Panel"
        lede="Inspect real-time vector embeddings, similarity scores, and source documents to audit grounded answers."
        meta="Vector + Semantic Retrieval"
      />
      <Card>
        <CardContent className="flex flex-col gap-4 pt-6">
          <div className="flex flex-col gap-2">
            <div className="grid gap-2 md:grid-cols-[1fr_140px]">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') inspect.mutate()
                }}
                placeholder="Ask a question or topic to inspect RAG retrieval (e.g. broadband plans, doctor timings)…"
              />
              <Button onClick={() => inspect.mutate()} disabled={inspect.isPending}>
                {inspect.isPending ? 'Searching…' : 'Inspect RAG'}
              </Button>
            </div>

            {/* Quick Suggestions */}
            <div className="flex items-center gap-1.5 flex-wrap pt-1">
              <span className="text-xs text-muted-foreground mr-1">Try quick queries:</span>
              {quickQueries.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => handleQuickSearch(item)}
                  className="rounded-md border bg-muted/40 hover:bg-muted px-2.5 py-0.5 text-xs text-foreground font-medium transition-colors"
                >
                  {item}
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-3 pt-2">
            {(result?.documents || []).map((doc, index) => (
              <div key={`${doc.source}-${index}`} className="rounded-xl border bg-card/70 p-4 shadow-xs">
                <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 border-b pb-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-xs">
                      📄 {doc.source}
                    </Badge>
                  </div>
                  <Badge variant="secondary" className="font-mono text-xs text-primary">
                    Relevance Score: {Number(doc.score || 0).toFixed(3)}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed font-sans select-text">
                  {doc.text}
                </p>
              </div>
            ))}
            {result && !result.documents?.length ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No matching chunks found. Try seeding demo data or searching another topic.
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </AppShell>
  )
}

function SafetyCenter() {
  const [result, setResult] = useState(null)
  const demo = useMutation({
    mutationFn: async () => {
      const response = await fetch(`${apiBaseUrl}/api/security/prompt-injection-demo`, { method: 'POST' })
      if (!response.ok) throw new Error(await response.text())
      return response.json()
    },
    onSuccess: setResult,
  })
  return (
    <AppShell title="Safety">
      <PageIntro title="Prompt-injection and healthcare guardrails" lede="Demonstrate that retrieved/uploaded content is untrusted and cannot override system rules." meta="Responsible AI" />
      <Card><CardHeader><CardTitle>Prompt injection demo</CardTitle><CardDescription>Insert a malicious knowledge-base document, then ask the chatbot what the document says. The agent should summarize safely and never reveal secrets.</CardDescription></CardHeader><CardContent className="flex flex-col gap-3"><Button className="w-fit" onClick={() => demo.mutate()} disabled={demo.isPending}>Create malicious demo doc</Button>{result ? <div className="rounded-xl border bg-muted/30 p-3 text-sm"><strong>Prompt injection blocked:</strong> {result.verdict}</div> : null}</CardContent></Card>
    </AppShell>
  )
}

function Handoffs() {
  const { data = [], isLoading, error, refetch } = useQuery({ queryKey: ['handoffs'], queryFn: () => getJson('/api/handoffs') })
  const create = useMutation({
    mutationFn: async () => {
      const response = await adminFetch('/api/handoffs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason: 'Manual demo escalation', summary: 'Caller needs human review', priority: 'high' }) })
      if (!response.ok) throw new Error(await response.text())
      return response.json()
    },
    onSuccess: () => refetch(),
  })
  return (
    <AppShell title="Handoffs">
      <PageIntro title="Human-in-the-loop escalation queue" lede="Escalate complaints, emergencies, or uncertain cases to a human team." meta={isLoading ? 'Loading' : error ? 'API unavailable' : `${data.length} tickets`} />
      <Button className="w-fit" onClick={() => create.mutate()}>Create demo handoff</Button>
      <Card><CardContent className="px-0"><Table><TableHeader><TableRow><TableHead>Created</TableHead><TableHead>Caller</TableHead><TableHead>Priority</TableHead><TableHead>Status</TableHead><TableHead>Reason</TableHead></TableRow></TableHeader><TableBody>{data.map((row) => <TableRow key={row._id}><TableCell>{formatTime(row.createdAt)}</TableCell><TableCell>{row.caller_id}</TableCell><TableCell>{row.priority}</TableCell><TableCell><Badge variant="outline">{row.status}</Badge></TableCell><TableCell>{row.reason}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card>
    </AppShell>
  )
}

function TokenMetrics() {
  const { data = [], isLoading, error } = useQuery({ queryKey: ['token-metrics'], queryFn: () => getJson('/api/token-metrics/recent') })
  return (
    <AppShell title="Token Metrics">
      <PageIntro title="Prompt compression and token budget" lede="Track estimated system, memory, conversation, and latest-user tokens to explain cost and latency controls." meta={isLoading ? 'Loading' : error ? 'API unavailable' : `${data.length} rows`} />
      <Card><CardContent className="px-0"><Table><TableHeader><TableRow><TableHead>Time</TableHead><TableHead>Caller</TableHead><TableHead>System</TableHead><TableHead>Memory</TableHead><TableHead>Conversation</TableHead><TableHead>Total</TableHead></TableRow></TableHeader><TableBody>{data.map((row, index) => <TableRow key={`${row.createdAt}-${index}`}><TableCell>{formatTime(row.createdAt)}</TableCell><TableCell>{row.caller_id}</TableCell><TableCell>{row.system_prompt_tokens}</TableCell><TableCell>{row.memory_tokens}</TableCell><TableCell>{row.conversation_tokens}</TableCell><TableCell className="font-semibold">{row.estimated_total_tokens}</TableCell></TableRow>)}</TableBody></Table></CardContent></Card>
    </AppShell>
  )
}

function PromptLab() {
  const queryClient = useQueryClient()
  const { data = [], isLoading, error } = useQuery({
    queryKey: ['prompts'],
    queryFn: () => getJson('/api/prompts'),
  })

  const [isAddOpen, setIsAddOpen] = useState(false)
  const [viewingPrompt, setViewingPrompt] = useState(null)
  const [copied, setCopied] = useState(false)

  const [formName, setFormName] = useState('')
  const [formDomain, setFormDomain] = useState('')
  const [formVersion, setFormVersion] = useState('')
  const [formNotes, setFormNotes] = useState('')
  const [formPrompt, setFormPrompt] = useState('')
  const [formIsActive, setFormIsActive] = useState(false)

  const activateMutation = useMutation({
    mutationFn: async (id) => {
      const res = await adminFetch(`/api/prompts/activate/${id}`, { method: 'POST' })
      if (!res.ok) throw new Error(await res.text())
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })

  const createMutation = useMutation({
    mutationFn: async (e) => {
      e?.preventDefault?.()
      if (!formPrompt.trim()) return
      const res = await adminFetch('/api/prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formName.trim() || 'Custom Voice Agent',
          domain: formDomain.trim() || 'General Support',
          version: formVersion.trim() || `v-${Date.now().toString().slice(-6)}`,
          notes: formNotes.trim() || 'Custom agent prompt.',
          prompt: formPrompt.trim(),
          is_active: formIsActive,
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      setIsAddOpen(false)
      setFormName('')
      setFormDomain('')
      setFormVersion('')
      setFormNotes('')
      setFormPrompt('')
      setFormIsActive(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id) => {
      const res = await adminFetch(`/api/prompts/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(await res.text())
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })

  const seedDemo = useMutation({
    mutationFn: async () => {
      const res = await adminFetch('/api/admin/seed-demo-data', { method: 'POST' })
      if (!res.ok) throw new Error(await res.text())
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      queryClient.invalidateQueries({ queryKey: ['analytics-summary'] })
      queryClient.invalidateQueries({ queryKey: ['recent-interactions'] })
      queryClient.invalidateQueries({ queryKey: ['bookings'] })
      queryClient.invalidateQueries({ queryKey: ['handoffs'] })
      queryClient.invalidateQueries({ queryKey: ['token-metrics'] })
      queryClient.invalidateQueries({ queryKey: ['doctors'] })
    },
  })

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <AppShell title="Prompt Lab">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex max-w-2xl flex-col gap-2">
          <h2 className="text-2xl font-semibold tracking-tight">Agent Personas & Prompt Lab</h2>
          <p className="text-muted-foreground text-sm">
            Manage, version, and switch between multi-domain voice agent personas in real time.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => seedDemo.mutate()}
            disabled={seedDemo.isPending}
            className="gap-1.5"
          >
            <Sparkle size={16} weight="duotone" className="text-primary" />
            {seedDemo.isPending ? 'Resetting…' : 'Seed Default Agents & Data'}
          </Button>
          <Button
            size="sm"
            onClick={() => setIsAddOpen(true)}
            className="gap-1.5 shadow-sm"
          >
            <Plus size={16} weight="bold" />
            Add New Agent Prompt
          </Button>
        </div>
      </div>

      {/* Featured Agent Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data.map((agent) => {
          const isActive = agent.is_active
          return (
            <Card
              key={agent._id || agent.version}
              className={`relative overflow-hidden transition-all duration-200 border-2 ${
                isActive
                  ? 'border-primary/80 bg-primary/5 shadow-md ring-1 ring-primary/30'
                  : 'border-border/60 hover:border-border'
              }`}
            >
              {isActive && (
                <div className="absolute top-0 right-0 bg-primary text-primary-foreground text-[11px] font-semibold px-3 py-0.5 rounded-bl-lg tracking-wide uppercase flex items-center gap-1">
                  <CheckCircle size={13} weight="fill" /> Active Live Persona
                </div>
              )}
              <CardHeader className="pb-3">
                <div className="flex items-start gap-3">
                  <div className={`p-2.5 rounded-xl ${isActive ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'}`}>
                    <Robot size={24} weight="duotone" />
                  </div>
                  <div>
                    <CardTitle className="text-lg font-bold">
                      {agent.name || (agent.version.includes('catla') ? 'Catla Broadband Help Desk' : 'One Hospitals Gurgaon Booking Agent')}
                    </CardTitle>
                    <CardDescription className="flex items-center gap-2 mt-1">
                      <Badge variant="secondary" className="text-xs">
                        {agent.domain || (agent.version.includes('catla') ? 'Telecom / ISP' : 'Healthcare')}
                      </Badge>
                      <span className="text-xs font-mono text-muted-foreground">{agent.version}</span>
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {agent.notes || 'Production-ready system prompt with guardrails, slot-filling, and language lock.'}
                </p>

                <div className="rounded-lg bg-background/80 border p-2.5 text-xs font-mono text-muted-foreground line-clamp-3">
                  {agent.prompt}
                </div>

                <div className="flex items-center justify-between pt-1">
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setViewingPrompt(agent)}
                      className="gap-1.5 text-xs h-8"
                    >
                      <Eye size={14} weight="duotone" /> Inspect Prompt
                    </Button>
                    {!agent.version?.startsWith('v1.') && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteMutation.mutate(agent._id || agent.version)}
                        className="text-destructive hover:text-destructive h-8 px-2"
                        title="Delete custom agent"
                      >
                        <Trash size={14} weight="duotone" />
                      </Button>
                    )}
                  </div>

                  {isActive ? (
                    <Badge variant="default" className="gap-1 bg-emerald-600 hover:bg-emerald-600 text-white">
                      <Check size={12} weight="bold" /> Currently Live
                    </Badge>
                  ) : (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => activateMutation.mutate(agent._id || agent.version)}
                      disabled={activateMutation.isPending}
                      className="gap-1.5 text-xs h-8 font-medium"
                    >
                      <CheckCircle size={14} weight="duotone" className="text-primary" />
                      Set as Live Agent
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Version History Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">All Prompt Versions & History</CardTitle>
          <CardDescription>Auditable prompt version registry for production deployments and A/B testing.</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Agent Persona</TableHead>
                <TableHead>Domain</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((row) => (
                <TableRow key={row._id || row.version}>
                  <TableCell className="font-medium">
                    {row.name || (row.version.includes('catla') ? 'Catla Broadband Support' : 'One Hospitals Booking')}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs">
                      {row.domain || (row.version.includes('catla') ? 'Telecom' : 'Healthcare')}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{row.version}</TableCell>
                  <TableCell>
                    <Badge variant={row.is_active ? 'default' : 'secondary'}>
                      {row.is_active ? '● Live' : 'Standby'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{formatTime(row.createdAt)}</TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setViewingPrompt(row)}
                      className="h-7 px-2 text-xs"
                    >
                      <Eye size={14} className="mr-1" /> View
                    </Button>
                    {!row.is_active && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => activateMutation.mutate(row._id || row.version)}
                        className="h-7 px-2.5 text-xs"
                      >
                        Activate
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Add New Prompt Modal */}
      {isAddOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="bg-background border rounded-2xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold">Add New Agent Persona & Prompt</h3>
                <p className="text-xs text-muted-foreground">Configure custom persona, domain instructions, and guardrails.</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setIsAddOpen(false)} className="h-8 w-8 p-0 rounded-full">
                ✕
              </Button>
            </div>

            <form onSubmit={createMutation.mutate} className="p-6 overflow-y-auto space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Agent Name</Label>
                  <Input
                    placeholder="e.g., QuickRide Cab Booking Assistant"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Domain / Category</Label>
                  <Input
                    placeholder="e.g., Travel / Mobility"
                    value={formDomain}
                    onChange={(e) => setFormDomain(e.target.value)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Version Tag</Label>
                  <Input
                    placeholder="e.g., v1.0-cab-booking"
                    value={formVersion}
                    onChange={(e) => setFormVersion(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Notes / Purpose</Label>
                  <Input
                    placeholder="e.g., Automated cab dispatch and fare estimates"
                    value={formNotes}
                    onChange={(e) => setFormNotes(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">System Prompt & Instructions (Markdown / Text)</Label>
                <textarea
                  className="w-full min-h-[220px] rounded-xl border bg-background px-3 py-2 text-sm font-mono focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
                  placeholder="You are a warm, polite voice assistant for..."
                  value={formPrompt}
                  onChange={(e) => setFormPrompt(e.target.value)}
                  required
                />
              </div>

              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="set-active-cb"
                  checked={formIsActive}
                  onChange={(e) => setFormIsActive(e.target.checked)}
                  className="rounded border-input text-primary focus:ring-primary h-4 w-4"
                />
                <Label htmlFor="set-active-cb" className="text-sm cursor-pointer">
                  Immediately set this persona as the active live agent
                </Label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t">
                <Button type="button" variant="outline" onClick={() => setIsAddOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={createMutation.isPending || !formPrompt.trim()}>
                  {createMutation.isPending ? 'Saving Agent…' : 'Save & Register Persona'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* View Prompt Modal */}
      {viewingPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="bg-background border rounded-2xl max-w-3xl w-full max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold flex items-center gap-2">
                  <FileText size={20} weight="duotone" className="text-primary" />
                  {viewingPrompt.name || viewingPrompt.version}
                </h3>
                <p className="text-xs text-muted-foreground">{viewingPrompt.domain || 'Agent Persona'} • {viewingPrompt.version}</p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyToClipboard(viewingPrompt.prompt)}
                  className="gap-1.5 h-8 text-xs"
                >
                  {copied ? <Check size={14} className="text-emerald-500" /> : <Sparkle size={14} />}
                  {copied ? 'Copied!' : 'Copy Prompt'}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setViewingPrompt(null)} className="h-8 w-8 p-0 rounded-full">
                  ✕
                </Button>
              </div>
            </div>

            <div className="p-6 overflow-y-auto flex-1 bg-muted/20">
              <pre className="text-xs font-mono whitespace-pre-wrap leading-relaxed text-foreground/90 select-text">
                {viewingPrompt.prompt}
              </pre>
            </div>

            <div className="px-6 py-3 border-t bg-background flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                Character count: {viewingPrompt.prompt?.length || 0} chars
              </span>
              <Button size="sm" onClick={() => setViewingPrompt(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  )
}

function toAgentState(status) {
  if (status === 'recording') return 'listening'
  if (status === 'processing' || status === 'sent') return 'thinking'
  if (status === 'playing') return 'talking'
  return null
}

function AgentTester() {
  const queryClient = useQueryClient()
  const { data: prompts = [] } = useQuery({
    queryKey: ['prompts'],
    queryFn: () => getJson('/api/prompts'),
  })

  const activeAgent = prompts.find((p) => p.is_active) || prompts[0]

  const switchAgentMutation = useMutation({
    mutationFn: async (id) => {
      const res = await adminFetch(`/api/prompts/activate/${id}`, { method: 'POST' })
      if (!res.ok) throw new Error(await res.text())
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })

  const [callerId, setCallerId] = useState('')
  const [status, setStatus] = useState('idle')
  const [toolStatus, setToolStatus] = useState('none')
  const [transcript, setTranscript] = useState('')
  const [reply, setReply] = useState('')
  const [fileDescription, setFileDescription] = useState('none')
  const [file, setFile] = useState(null)
  const [phoneNumber, setPhoneNumber] = useState('')
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState([
    { role: 'assistant', content: 'Hi, I can help with appointments, telecom helpdesk, FAQs, and voice interactions.' },
  ])
  const [isRecording, setIsRecording] = useState(false)
  const fileInputRef = useRef(null)
  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const analyserRef = useRef(null)
  const audioDataRef = useRef(null)

  // ── Enterprise WebSocket: heartbeat + exponential backoff reconnection ──
  const handleWsMessage = useCallback(async (event) => {
    if (typeof event.data === 'string') {
      try {
        const payload = JSON.parse(event.data)
        if (payload.type === 'status') setStatus(payload.message)
        if (payload.type === 'tool_status') setToolStatus(`${payload.tool} ${payload.status} (${JSON.stringify(payload.args)})`)
        if (payload.type === 'transcript') setTranscript(payload.text)
        if (payload.type === 'reply') setReply(payload.text)
        if (payload.type === 'done') setStatus('idle')
      } catch {
        console.info(event.data)
      }
    } else {
      setStatus('playing')
      const audioContext = new (window.AudioContext || window.webkitAudioContext)()
      const decoded = await audioContext.decodeAudioData(event.data.slice(0))
      const source = audioContext.createBufferSource()
      source.buffer = decoded
      source.connect(audioContext.destination)
      source.onended = () => setStatus('idle')
      source.start()
    }
  }, [])

  const { send: wsSend, readyState: wsReadyState, reconnectAttempts } = useResilientWebSocket(wsUrl, {
    onMessage: handleWsMessage,
    onOpen: () => {
      wsSend(JSON.stringify({ type: 'session_start', caller_id: callerId || 'anonymous' }))
      setStatus('connected')
    },
    onClose: () => setStatus('ws closed'),
  })

  useEffect(() => {
    if (wsReadyState === WebSocket.CLOSED && reconnectAttempts > 0) {
      setStatus(`reconnecting... (attempt ${reconnectAttempts})`)
    }
  }, [wsReadyState, reconnectAttempts])

  const getInputVolume = useCallback(() => {
    const analyser = analyserRef.current
    if (!analyser) return 0
    analyser.getByteFrequencyData(audioDataRef.current)
    const sum = audioDataRef.current.reduce((a, b) => a + b, 0)
    return Math.min(1, sum / (audioDataRef.current.length * 128))
  }, [])

  const agentState = toAgentState(status)

  const uploadFile = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Select a file first.')
      const form = new FormData()
      form.append('caller_id', callerId || 'anonymous')
      form.append('file', file)
      const response = await fetch(`${apiBaseUrl}/api/upload-file`, { method: 'POST', body: form })
      if (!response.ok) throw new Error(await response.text())
      return response.json()
    },
    onSuccess: (result) => {
      setFileDescription(result.description || 'No description returned.')
      setStatus('file uploaded')
    },
    onError: () => setStatus('upload failed'),
  })

  const sendChatMessage = useMutation({
    mutationFn: async (message) => {
      const response = await fetch(`${apiBaseUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ caller_id: callerId || 'anonymous', message }),
      })
      if (!response.ok) throw new Error(await response.text())
      return response.json()
    },
    onSuccess: (result) => {
      const replyText = result.reply || 'I can help with that. Please share a doctor, department, or preferred date and time.'
      setChatMessages((items) => [...items, { role: 'assistant', content: replyText }])
      setReply(replyText)
      setToolStatus(result.tool_used || 'chat')
      setStatus('chat replied')
    },
    onError: () => {
      setChatMessages((items) => [...items, { role: 'assistant', content: 'I could not process that message. Please try again.' }])
      setStatus('chat failed')
    },
  })

  const submitChat = () => {
    const message = chatInput.trim()
    if (!message || sendChatMessage.isPending) return
    setChatInput('')
    setIsChatOpen(true)
    setChatMessages((items) => [...items, { role: 'user', content: message }])
    sendChatMessage.mutate(message)
  }

  const startOutboundCall = useMutation({
    mutationFn: async () => {
      if (!phoneNumber.trim()) throw new Error('Enter a phone number first.')
      const response = await fetch(`${apiBaseUrl}/api/telephony/call`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: phoneNumber.trim(), caller_id: callerId || 'dashboard' }),
      })
      if (!response.ok) throw new Error(await response.text())
      return response.json()
    },
    onSuccess: (result) => setStatus(result.ok ? 'call queued' : result.reason || 'call needs config'),
    onError: () => setStatus('call failed'),
  })

  const startRecording = async () => {
    if (isRecording) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
      const source = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      analyserRef.current = analyser
      audioDataRef.current = new Uint8Array(analyser.frequencyBinCount)

      const recorder = new MediaRecorder(stream)
      recorderRef.current = recorder
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) chunksRef.current.push(event.data)
      }
      recorder.start()
      setIsRecording(true)
      // send start control frame (hook is always connected)
      wsSend(JSON.stringify({ type: 'start', mimeType: recorder.mimeType || 'audio/webm' }))
      setStatus('recording')
    } catch (err) {
      setStatus('mic error')
      console.error(err)
    }
  }

  const stopRecording = () => {
    const recorder = recorderRef.current
    if (!recorder || !isRecording) return
    setIsRecording(false)
    analyserRef.current = null
    recorder.addEventListener(
      'stop',
      async () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        const arrayBuffer = await blob.arrayBuffer()
        // Send audio binary + stop signal via resilient hook
        wsSend(arrayBuffer)
        wsSend(JSON.stringify({ type: 'stop' }))
        setStatus('processing')
        recorder.stream.getTracks().forEach((track) => track.stop())
      },
      { once: true },
    )
    recorder.stop()
  }

  const statusItems = useMemo(
    () => [
      ['Status', status],
      ['Tool status', toolStatus],
      ['Live transcript', transcript || 'Waiting for speech.'],
      ['Reply', reply || 'Waiting for response.'],
      ['File understanding', fileDescription],
    ],
    [status, toolStatus, transcript, reply, fileDescription],
  )

  const orbLabel = isRecording ? 'Release to send' : status === 'processing' ? 'Processing…' : status === 'playing' ? 'Agent speaking' : 'Tap to talk'

  return (
    <AppShell title="Agent Console">
      <PageIntro
        title="Test voice session end to end"
        lede="Test voice pipeline, RAG knowledge grounding, tool execution, and agent switching in real-time."
        meta="Multi-Agent Voice + Chat"
      />

      {/* Active Persona Banner & Quick Switcher */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3.5 rounded-xl border bg-card/60 backdrop-blur-xs">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <Robot size={22} weight="duotone" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Active Live Brain:</span>
              <span className="text-sm font-bold">{activeAgent?.name || activeAgent?.version || 'Default Agent'}</span>
              <Badge variant="default" className="text-[10px] h-4 bg-emerald-600">Live</Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              {activeAgent?.domain || 'General'} • {activeAgent?.version}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-xs text-muted-foreground mr-1">Switch Agent:</span>
          {prompts.map((p) => {
            const isSelected = p.is_active
            return (
              <Button
                key={p._id || p.version}
                variant={isSelected ? 'default' : 'outline'}
                size="sm"
                className={`h-7 text-xs ${isSelected ? 'bg-primary text-primary-foreground' : ''}`}
                onClick={() => switchAgentMutation.mutate(p._id || p.version)}
                disabled={isSelected || switchAgentMutation.isPending}
              >
                {p.version?.includes('catla') ? 'Catla Helpdesk' : p.version?.includes('hospitals') ? 'One Hospitals' : (p.name?.slice(0, 14) || p.version)}
              </Button>
            )
          })}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <Card className="bg-muted/40 lg:col-span-4">
          <CardContent className="flex flex-col gap-4">
            <div className="rounded-xl border bg-background/60 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Inbound phone test</p>
              <p className="mt-1 text-sm font-semibold">Dial 09513886363 to test the live Exotel agent.</p>
              <p className="mt-1 text-xs text-muted-foreground">Inbound calls route to the live voice agent configured in Exotel.</p>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="caller-id">Caller ID</Label>
              <Input
                id="caller-id"
                value={callerId}
                onChange={(event) => setCallerId(event.target.value)}
                placeholder="anonymous"
              />
            </div>

            <div className="flex flex-col items-center gap-2">
              <div
                className="relative cursor-pointer select-none"
                style={{ width: 180, height: 180 }}
                onMouseDown={(event) => { event.preventDefault(); startRecording() }}
                onMouseUp={(event) => { event.preventDefault(); stopRecording() }}
                onMouseLeave={() => { if (isRecording) stopRecording() }}
                onTouchStart={(event) => { event.preventDefault(); startRecording() }}
                onTouchEnd={(event) => { event.preventDefault(); stopRecording() }}
                title={orbLabel}
              >
                <Orb
                  agentState={agentState}
                  getInputVolume={getInputVolume}
                  colors={["#818cf8", "#c4b5fd"]}
                  className="h-full w-full"
                />
              </div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{orbLabel}</p>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>Upload file</Label>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept="image/*,application/pdf,text/plain,text/markdown,.md"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              <div className="grid grid-cols-[1fr_48px] gap-2">
                <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()} className="justify-start truncate">
                  {file ? file.name : 'Choose file'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  title="Upload selected file"
                  onClick={() => uploadFile.mutate()}
                  disabled={uploadFile.isPending || !file}
                  aria-label="Upload selected file"
                >
                  <UploadSimple size={18} weight="duotone" />
                </Button>
              </div>
            </div>

            <Button type="button" variant="outline" onClick={() => setIsChatOpen((value) => !value)}>
              <ChatCircle size={18} weight="duotone" /> {isChatOpen ? 'Hide chat' : 'Chat with agent'}
            </Button>

            <div className="flex flex-col gap-1.5 opacity-80">
              <Label htmlFor="phone-number">Outbound call</Label>
              <Input
                id="phone-number"
                value={phoneNumber}
                onChange={(event) => setPhoneNumber(event.target.value)}
                placeholder="+91XXXXXXXXXX"
              />
              <p className="text-xs text-muted-foreground">Provider restrictions may block outbound on trial/KYC accounts.</p>
            </div>
            <Button type="button" variant="outline" onClick={() => startOutboundCall.mutate()} disabled={startOutboundCall.isPending}>
              <PhoneCall size={18} weight="duotone" /> {startOutboundCall.isPending ? 'Calling' : 'Initiate call'}
            </Button>
          </CardContent>
        </Card>

        <Card className="lg:col-span-8">
          <CardContent className="flex flex-col divide-y" aria-live="polite">
            {statusItems.map(([label, value]) => (
              <div key={label} className="flex items-start gap-3 py-3 first:pt-0">
                <Waveform size={18} className="mt-0.5 shrink-0 text-muted-foreground" weight="duotone" />
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <strong className="break-words text-sm font-medium">{value}</strong>
                </div>
              </div>
            ))}

            <div className="pt-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">Text chatbot</p>
                  <p className="text-xs text-muted-foreground">Uses the same tools, RAG, and persistent caller memory.</p>
                </div>
                <Button type="button" variant="outline" size="sm" onClick={() => setIsChatOpen((value) => !value)}>
                  <ChatCircle size={16} weight="duotone" /> {isChatOpen ? 'Collapse' : 'Open'}
                </Button>
              </div>

              {isChatOpen ? (
                <div className="rounded-xl border bg-muted/30 p-3">
                  <div className="mb-3 flex max-h-72 flex-col gap-2 overflow-y-auto pr-1">
                    {chatMessages.map((message, index) => (
                      <div
                        key={`${message.role}-${index}`}
                        className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                          message.role === 'user'
                            ? 'ml-auto bg-primary text-primary-foreground'
                            : 'bg-background text-foreground border'
                        }`}
                      >
                        {message.content}
                      </div>
                    ))}
                    {sendChatMessage.isPending ? (
                      <div className="max-w-[85%] rounded-2xl border bg-background px-3 py-2 text-sm text-muted-foreground">
                        Agent is thinking…
                      </div>
                    ) : null}
                  </div>
                  <div className="grid grid-cols-[1fr_44px] gap-2">
                    <Input
                      value={chatInput}
                      onChange={(event) => setChatInput(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') submitChat()
                      }}
                      placeholder="Ask about booking, doctors, uploaded PDFs…"
                    />
                    <Button type="button" onClick={submitChat} disabled={sendChatMessage.isPending || !chatInput.trim()} aria-label="Send chat message">
                      <PaperPlaneTilt size={18} weight="duotone" />
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/overview" replace />} />
      <Route path="/overview" element={<Overview />} />
      <Route path="/interactions" element={<Interactions />} />
      <Route path="/bookings" element={<Bookings />} />
      <Route path="/calendar" element={<CalendarView />} />
      <Route path="/rag" element={<RagInspector />} />
      <Route path="/safety" element={<SafetyCenter />} />
      <Route path="/handoffs" element={<Handoffs />} />
      <Route path="/tokens" element={<TokenMetrics />} />
      <Route path="/prompts" element={<PromptLab />} />
      <Route path="/agent" element={<AgentTester />} />
    </Routes>
  )
}

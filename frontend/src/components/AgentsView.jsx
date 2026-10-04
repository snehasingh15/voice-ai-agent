import { useEffect, useMemo, useState } from 'react'
import {
  GraduationCap,
  Heartbeat,
  CurrencyDollar,
  AirplaneTilt,
  Broadcast,
  Brain,
  GearSix,
  PlayCircle,
  ShieldCheck,
  CalendarCheck,
  MagnifyingGlass,
  Plus,
  PencilSimple,
  X,
} from '@phosphor-icons/react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export const INDUSTRIES = [
  { id: 'education', label: 'Education', icon: GraduationCap },
  { id: 'healthcare', label: 'Healthcare', icon: Heartbeat },
  { id: 'finance', label: 'Finance', icon: CurrencyDollar },
  { id: 'travel', label: 'Travel', icon: AirplaneTilt },
  { id: 'telecom', label: 'Telecom', icon: Broadcast },
]

export const AGENT_CATALOG = [
  { id: 'fore-school-counsellor', industry: 'education', name: 'FORE School Counsellor', organization: 'FORE School of Management', initials: 'FS', languages: 'English, Hindi, Hinglish', welcome: 'Hello, am I speaking with {student_name}?', objective: 'Qualify PGDM-HHM interest, answer program questions, and book a counsellor discussion.', serviceTool: 'service_booking: counsellor_discussion', metadata: ['Uses registered student_name and phone_number', 'Books counsellor callback/discussion', 'Stores education intent and callback preference'], prompt: 'Priya is a warm admissions counsellor. She explains PGDM-HHM clearly, asks one question at a time, and books a counsellor session only after date/time confirmation.', guardrails: ['Never ask for registered name or phone again when already provided.', 'Never pressure the student after a clear refusal.', 'Never claim brochure/session/callback is sent or booked until the service booking tool succeeds.'], hangup: 'Hang up after confirmed counsellor booking, brochure/details sent confirmation, wrong number apology, opt-out, callback scheduled, extended silence farewell, or abusive behavior.' },
  { id: 'apollo-health-patient', industry: 'healthcare', name: 'Apollo Health Patient Assistant', organization: 'Apollo Health', initials: 'AH', languages: 'English, Hindi, Hinglish', welcome: 'Hi {{patient_name}}, I am calling from Apollo Health regarding your recent enquiry. Is this a good time to speak for a moment?', objective: 'Understand patient intent, answer health-service questions, and assist with appointment or callback booking.', serviceTool: 'service_booking: appointment_or_callback', metadata: ['Patient enquiry follow-up', 'Appointment assistance'], prompt: 'A warm patient engagement representative who listens first, responds empathetically, and never claims booking completion without tool confirmation.', guardrails: ['Do not provide diagnosis or emergency medical advice beyond escalation guidance.', 'Never store OTPs, card numbers, national IDs, or highly sensitive data.', 'Never hang up because the script is complete.'], hangup: 'Hang up only when the patient clearly ends, declines further help, confirmed task is complete with closing response, wrong number completed, or silence flow completed.' },
  { id: 'fortis-consultancy-support', industry: 'finance', name: 'Fortis Consultancy Support', organization: 'Fortis Consultancy', initials: 'FC', languages: 'English, Hindi, Hinglish', welcome: 'Hello, is this {caller_name} I am speaking with?', objective: 'Identify tax/accounting/payroll/GST support need and book a consultation or callback.', serviceTool: 'service_booking: finance_consultation', metadata: ['Tax and accounting triage', 'Callback/reschedule support'], prompt: 'Neha is a professional client support representative for finance and compliance service enquiries.', guardrails: ['Do not provide legal/tax filing guarantees without advisor review.', 'Do not collect full card numbers, passwords, OTPs, PAN/Aadhaar.', 'Stop immediately on opt-out or stop phrases.'], hangup: 'Hang up on explicit stop, achieved objective, confirmed reschedule plus user closing, completed rating flow, or senior-support ticket closing plus user closing.' },
  { id: 'pravaas-journey-travel', industry: 'travel', name: 'Pravaas Journey Planner', organization: 'Pravaas Journey', initials: 'PJ', languages: 'English, Hindi, Hinglish', welcome: 'Hello, is this {caller_name} I am speaking with?', objective: 'Understand travel requirement, capture destination/date/budget, and book a trip-planning callback.', serviceTool: 'service_booking: travel_consultation', metadata: ['Travel enquiry qualification', 'Package callback booking'], prompt: 'A helpful travel advisor who resolves enquiries and captures travel preferences.', guardrails: ['Never continue selling after clear disinterest.', 'Never claim booking, payment, transfer, callback, or follow-up is complete unless confirmed.', 'Respect do-not-contact requests immediately.'], hangup: 'Hang up after clear goodbye, not interested, do-not-contact, agreed callback, resolved enquiry, completed booking/handoff, silence flow, or natural conclusion.' },
  { id: 'aspirare-helpdesk', industry: 'telecom', name: 'Aspirare Help Desk', organization: 'Aspirare', initials: 'AS', languages: 'English, Hindi', welcome: 'Hello, this is Aspirare Help Desk. How may I assist you today?', objective: 'Handle telecom/helpdesk questions, capture issue details, and book callback/escalation when needed.', serviceTool: 'service_booking: support_callback', metadata: ['Helpdesk issue triage', 'Support callback booking'], prompt: 'A concise telecom helpdesk assistant that stays available until the customer clearly ends the conversation.', guardrails: ['Never hang up on okay, yes, no, hmm, short pauses, language switch, frustration, or unknown question.', 'Never terminate while customer is speaking.', 'Confirm ticket/callback before creating it.'], hangup: 'Hang up only when customer clearly says bye, that is all, no more questions, you can end the call, or any clear finish statement.' },
]

const defaultApiBaseUrl =
  typeof window !== 'undefined' && ['localhost', '127.0.0.1'].includes(window.location.hostname)
    ? 'http://localhost:8000'
    : 'https://voice-ai-agent-ybml.onrender.com'
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl
const blankAgent = {
  industry: 'education', name: '', organization: '', initials: '', languages: 'English, Hindi, Hinglish',
  welcome: '', objective: '', serviceTool: 'service_booking: callback', prompt: '', guardrailsText: '', hangup: '', metadataText: '',
}

function authHeaders(extra = {}) {
  const token = window.localStorage?.getItem('voice_ai_admin_token')
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

function normalizeAgent(agent) {
  return {
    ...agent,
    initials: agent.initials || (agent.name || 'Agent').split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase(),
    metadata: Array.isArray(agent.metadata) ? agent.metadata : [],
    guardrails: Array.isArray(agent.guardrails) ? agent.guardrails : [],
  }
}

function agentToForm(agent) {
  return {
    ...blankAgent,
    ...agent,
    guardrailsText: (agent.guardrails || []).join('\n'),
    metadataText: (agent.metadata || []).join('\n'),
  }
}

function formToPayload(form) {
  return {
    industry: form.industry,
    name: form.name.trim(),
    organization: form.organization.trim(),
    initials: form.initials.trim(),
    languages: form.languages.trim(),
    welcome: form.welcome.trim(),
    objective: form.objective.trim(),
    serviceTool: form.serviceTool.trim(),
    prompt: form.prompt.trim(),
    hangup: form.hangup.trim(),
    metadata: form.metadataText.split('\n').map((x) => x.trim()).filter(Boolean),
    guardrails: form.guardrailsText.split('\n').map((x) => x.trim()).filter(Boolean),
  }
}

function AgentEditor({ mode, value, onChange, onClose, onSave, saving }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded-lg border bg-background p-5 shadow-xl">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold">{mode === 'new' ? 'New Agent' : 'Edit Agent'}</h3>
            <p className="text-sm text-muted-foreground">Select industry and configure the agent details used by console, memory, tools, and bookings.</p>
          </div>
          <Button variant="outline" size="sm" onClick={onClose}><X className="size-4" /></Button>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="grid gap-1 text-sm font-medium">Industry Type<select className="h-10 rounded-md border bg-background px-3" value={value.industry} onChange={(e) => onChange({ ...value, industry: e.target.value })}>{INDUSTRIES.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
          <label className="grid gap-1 text-sm font-medium">Agent Name<Input value={value.name} onChange={(e) => onChange({ ...value, name: e.target.value })} /></label>
          <label className="grid gap-1 text-sm font-medium">Organization<Input value={value.organization} onChange={(e) => onChange({ ...value, organization: e.target.value })} /></label>
          <label className="grid gap-1 text-sm font-medium">Initials<Input value={value.initials} onChange={(e) => onChange({ ...value, initials: e.target.value })} /></label>
          <label className="grid gap-1 text-sm font-medium md:col-span-2">Languages<Input value={value.languages} onChange={(e) => onChange({ ...value, languages: e.target.value })} /></label>
          <label className="grid gap-1 text-sm font-medium md:col-span-2">Welcome Message<textarea className="min-h-16 rounded-md border bg-background p-3" value={value.welcome} onChange={(e) => onChange({ ...value, welcome: e.target.value })} /></label>
          <label className="grid gap-1 text-sm font-medium md:col-span-2">Objective<textarea className="min-h-20 rounded-md border bg-background p-3" value={value.objective} onChange={(e) => onChange({ ...value, objective: e.target.value })} /></label>
          <label className="grid gap-1 text-sm font-medium md:col-span-2">Service Tool<Input value={value.serviceTool} onChange={(e) => onChange({ ...value, serviceTool: e.target.value })} /></label>
          <label className="grid gap-1 text-sm font-medium md:col-span-2">System Prompt<textarea className="min-h-28 rounded-md border bg-background p-3" value={value.prompt} onChange={(e) => onChange({ ...value, prompt: e.target.value })} /></label>
          <label className="grid gap-1 text-sm font-medium">Guardrails, one per line<textarea className="min-h-28 rounded-md border bg-background p-3" value={value.guardrailsText} onChange={(e) => onChange({ ...value, guardrailsText: e.target.value })} /></label>
          <label className="grid gap-1 text-sm font-medium">Metadata, one per line<textarea className="min-h-28 rounded-md border bg-background p-3" value={value.metadataText} onChange={(e) => onChange({ ...value, metadataText: e.target.value })} /></label>
          <label className="grid gap-1 text-sm font-medium md:col-span-2">Hangup Rule<textarea className="min-h-20 rounded-md border bg-background p-3" value={value.hangup} onChange={(e) => onChange({ ...value, hangup: e.target.value })} /></label>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button disabled={saving || !value.name.trim()} onClick={onSave}>{saving ? 'Saving' : mode === 'new' ? 'Create Agent' : 'Save Changes'}</Button>
        </div>
      </div>
    </div>
  )
}

export function AgentsView({ onSelectAgentForMemory, onTestAgent }) {
  const [industry, setIndustry] = useState('all')
  const [search, setSearch] = useState('')
  const [agents, setAgents] = useState(AGENT_CATALOG.map(normalizeAgent))
  const [selectedId, setSelectedId] = useState(AGENT_CATALOG[0]?.id || '')
  const [editorMode, setEditorMode] = useState(null)
  const [form, setForm] = useState(blankAgent)
  const [saving, setSaving] = useState(false)

  const loadAgents = async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/voice-agents`)
      if (!res.ok) throw new Error(String(res.status))
      const data = await res.json()
      const normalized = data.map(normalizeAgent)
      setAgents(normalized)
      if (!normalized.some((agent) => agent.id === selectedId)) setSelectedId(normalized[0]?.id || '')
    } catch {
      setAgents(AGENT_CATALOG.map(normalizeAgent))
    }
  }

  useEffect(() => { loadAgents() }, [])

  const filteredAgents = useMemo(() => {
    const query = search.trim().toLowerCase()
    return agents.filter((agent) => industry === 'all' || agent.industry === industry).filter((agent) => {
      if (!query) return true
      return [agent.name, agent.organization, agent.objective, agent.languages, agent.serviceTool].join(' ').toLowerCase().includes(query)
    })
  }, [agents, industry, search])

  const selectedAgent = agents.find((agent) => agent.id === selectedId) || filteredAgents[0] || agents[0]
  const selectedIndustry = INDUSTRIES.find((item) => item.id === selectedAgent?.industry) || INDUSTRIES[0]

  const openNew = () => { setForm(blankAgent); setEditorMode('new') }
  const openEdit = (agent) => { setForm(agentToForm(agent)); setEditorMode('edit') }
  const closeEditor = () => setEditorMode(null)

  const saveAgent = async () => {
    const payload = formToPayload(form)
    setSaving(true)
    try {
      const url = editorMode === 'edit' ? `${apiBaseUrl}/api/voice-agents/${encodeURIComponent(form.id)}` : `${apiBaseUrl}/api/voice-agents`
      const res = await fetch(url, { method: editorMode === 'edit' ? 'PATCH' : 'POST', headers: authHeaders({ 'Content-Type': 'application/json' }), body: JSON.stringify(payload) })
      if (!res.ok) throw new Error(await res.text())
      const saved = normalizeAgent(await res.json())
      await loadAgents()
      setSelectedId(saved.id)
      closeEditor()
    } finally {
      setSaving(false)
    }
  }

  const goToConfig = (agent) => { window.location.href = `/agent-config?agent=${encodeURIComponent(agent.id)}` }
  const goToTest = (agent) => { if (onTestAgent) onTestAgent(agent.id); else window.location.href = `/agent?agent=${encodeURIComponent(agent.id)}` }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 border-b pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Voice AI Agents</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">Choose an industry, select an agent card, then expand, edit, test, configure, or create a new agent.</p>
        </div>
        <div className="grid gap-2 sm:grid-cols-[220px_280px_auto]">
          <select value={industry} onChange={(event) => setIndustry(event.target.value)} className="h-10 rounded-md border border-input bg-background px-3 text-sm">
            <option value="all">All industries</option>
            {INDUSTRIES.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
          <div className="relative"><MagnifyingGlass className="absolute left-3 top-3 size-4 text-muted-foreground" /><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search agents..." className="pl-9" /></div>
          <Button onClick={openNew}><Plus className="size-4" /> New Agent</Button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
        {filteredAgents.map((agent) => {
          const meta = INDUSTRIES.find((item) => item.id === agent.industry) || INDUSTRIES[0]
          const Icon = meta.icon
          const active = selectedAgent?.id === agent.id
          return (
            <button key={agent.id} type="button" onClick={() => setSelectedId(agent.id)} className={`aspect-square rounded-lg border bg-card p-4 text-left transition hover:border-primary/70 ${active ? 'border-primary ring-1 ring-primary/50' : 'border-border/70'}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex size-11 items-center justify-center rounded-md border bg-primary/10 text-sm font-bold text-primary">{agent.initials}</div>
                <Icon className="size-5 text-muted-foreground" weight="duotone" />
              </div>
              <div className="mt-4 space-y-1">
                <p className="line-clamp-2 text-sm font-semibold">{agent.name}</p>
                <p className="line-clamp-1 text-xs text-muted-foreground">{meta.label}</p>
                <p className="line-clamp-2 text-xs text-muted-foreground">{agent.organization}</p>
              </div>
              <Badge variant={agent.source === 'custom' ? 'default' : 'secondary'} className="mt-3 text-[10px]">{agent.source === 'custom' ? 'Custom' : 'Default'}</Badge>
            </button>
          )
        })}
      </div>

      {selectedAgent ? (
        <Card className="border-primary/30">
          <CardHeader className="space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-center gap-3"><div className="flex size-12 items-center justify-center rounded-md border bg-primary/10 font-bold text-primary">{selectedAgent.initials}</div><div><CardTitle>{selectedAgent.name}</CardTitle><CardDescription>{selectedIndustry.label} / {selectedAgent.organization} / {selectedAgent.languages}</CardDescription></div></div>
              <div className="flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={() => openEdit(selectedAgent)}><PencilSimple className="size-4" /> Edit</Button><Button variant="outline" size="sm" onClick={() => onSelectAgentForMemory ? onSelectAgentForMemory(selectedAgent.id) : (window.location.href = `/memory?agent=${selectedAgent.id}`)}><Brain className="size-4" /> Memory</Button><Button variant="outline" size="sm" onClick={() => goToConfig(selectedAgent)}><GearSix className="size-4" /> Config</Button><Button size="sm" onClick={() => goToTest(selectedAgent)}><PlayCircle className="size-4" /> Test</Button></div>
            </div>
            <div className="rounded-md border bg-background/70 p-3 text-sm"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Welcome Message</p><p className="mt-1 font-medium">{selectedAgent.welcome}</p></div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2"><div className="rounded-md border bg-muted/20 p-3"><p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><CalendarCheck className="size-4" /> Service Tool</p><p className="text-sm font-medium">{selectedAgent.serviceTool}</p></div><div className="rounded-md border bg-muted/20 p-3"><p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><Brain className="size-4" /> Memory</p><p className="text-sm font-medium">Recall + real-time update</p></div></div>
            <div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Objective</p><p className="mt-1 text-sm">{selectedAgent.objective}</p></div>
            <div><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Metadata</p><div className="mt-2 flex flex-wrap gap-2">{(selectedAgent.metadata || []).map((item) => <Badge key={item} variant="outline" className="text-[11px]">{item}</Badge>)}</div></div>
            <div className="rounded-md border bg-background/70 p-3"><p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground"><ShieldCheck className="size-4" /> Guardrails</p><ul className="space-y-1 text-xs text-muted-foreground">{(selectedAgent.guardrails || []).map((rule) => <li key={rule}>- {rule}</li>)}</ul></div>
            <div className="rounded-md border bg-background/70 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Hangup Evaluator</p><p className="mt-1 text-xs text-muted-foreground">{selectedAgent.hangup}</p></div>
          </CardContent>
        </Card>
      ) : null}

      {editorMode ? <AgentEditor mode={editorMode} value={form} onChange={setForm} onClose={closeEditor} onSave={saveAgent} saving={saving} /> : null}
    </div>
  )
}

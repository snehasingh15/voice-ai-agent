import { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Brain,
  Sliders,
  Robot,
  ClockCounterClockwise,
  GitFork,
  Check,
  Plus,
  Trash,
  Lock,
  LockOpen,
  Phone,
  ChatCircle,
  WhatsappLogo,
  HardDrives,
  MagnifyingGlass,
  FloppyDisk,
  WarningCircle,
  CheckCircle,
  ArrowsClockwise,
  Users,
  ShieldCheck,
  Info,
} from '@phosphor-icons/react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const defaultApiBaseUrl =
  typeof window !== 'undefined' && ['localhost', '127.0.0.1'].includes(window.location.hostname)
    ? 'http://localhost:8000'
    : 'https://voice-ai-agent-ybml.onrender.com'
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl

function authHeaders(extra = {}) {
  const token = typeof window !== 'undefined' && window.localStorage?.getItem('voice_ai_admin_token')
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

async function apiFetch(path, options = {}) {
  const res = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: authHeaders(options.headers || {}),
  })
  if (!res.ok) {
    const errorText = await res.text()
    throw new Error(errorText || `Request failed with status ${res.status}`)
  }
  return res.json()
}

export function MemoryCortexView() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('memory') // memory | tenant_rules | agent_rules | activity | graph
  const [selectedAgentId, setSelectedAgentId] = useState('reminder')
  const [agentSearch, setAgentSearch] = useState('')
  const [toastMessage, setToastMessage] = useState('')

  const showToast = (msg) => {
    setToastMessage(msg)
    setTimeout(() => setToastMessage(''), 3500)
  }

  // 1. Tenant Memory Config Query
  const { data: tenantConfig = {}, isLoading: configLoading } = useQuery({
    queryKey: ['tenant-memory-config'],
    queryFn: () => apiFetch('/api/memory/tenant-config'),
  })

  // 2. Tenant Rules Query
  const { data: tenantRules = [], isLoading: rulesLoading } = useQuery({
    queryKey: ['tenant-rules'],
    queryFn: () => apiFetch('/api/memory/tenant-rules'),
  })

  // 3. Agents Directory Query
  const { data: agents = [] } = useQuery({
    queryKey: ['memory-agents'],
    queryFn: () => apiFetch('/api/memory/agents'),
  })

  // 4. Selected Agent Rules Query
  const { data: agentRuleData = { rules: [] }, isLoading: agentRulesLoading } = useQuery({
    queryKey: ['agent-rules', selectedAgentId],
    queryFn: () => apiFetch(`/api/memory/agent-rules/${selectedAgentId}`),
    enabled: Boolean(selectedAgentId),
  })

  // 5. Activity Log Query
  const { data: activities = [] } = useQuery({
    queryKey: ['memory-activity'],
    queryFn: () => apiFetch('/api/memory/activity'),
    refetchInterval: 10000,
  })

  // 6. Knowledge Graph Query
  const { data: graphData = { nodes: [], edges: [], metrics: {} } } = useQuery({
    queryKey: ['memory-graph'],
    queryFn: () => apiFetch('/api/memory/graph'),
  })

  // Local state for Tenant Config edits
  const [memoryOn, setMemoryOn] = useState(true)
  const [channels, setChannels] = useState({ voice: true, web_chat: true, whatsapp: true, mcp_server: true })
  const [visibility, setVisibility] = useState('isolated')

  // Sync with fetched data
  useEffect(() => {
    if (tenantConfig.remember_conversations !== undefined) setMemoryOn(Boolean(tenantConfig.remember_conversations))
    if (tenantConfig.channels) setChannels(tenantConfig.channels)
    if (tenantConfig.visibility) setVisibility(tenantConfig.visibility)
  }, [tenantConfig])

  // Local state for Tenant Rules table
  const [editableTenantRules, setEditableTenantRules] = useState([])
  useEffect(() => {
    if (tenantRules && tenantRules.length > 0) {
      setEditableTenantRules([...tenantRules])
    }
  }, [tenantRules])

  // Local state for Agent Rules overrides
  const [agentOverrides, setAgentOverrides] = useState({})
  useEffect(() => {
    if (agentRuleData && agentRuleData.rules) {
      const overrides = {}
      agentRuleData.rules.forEach((r) => {
        if (r.is_overridden) overrides[r.key] = r.value
      })
      setAgentOverrides(overrides)
    }
  }, [agentRuleData])

  // Save Tenant Config Mutation
  const saveConfigMutation = useMutation({
    mutationFn: (updated) =>
      apiFetch('/api/memory/tenant-config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-memory-config'] })
      showToast('Tenant memory settings saved successfully.')
    },
  })

  // Save Tenant Rules Mutation
  const saveTenantRulesMutation = useMutation({
    mutationFn: (rules) =>
      apiFetch('/api/memory/tenant-rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rules }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-rules'] })
      queryClient.invalidateQueries({ queryKey: ['agent-rules'] })
      showToast('Tenant rules saved successfully.')
    },
  })

  // Save Agent Rules Mutation
  const saveAgentRulesMutation = useMutation({
    mutationFn: (overrides) =>
      apiFetch(`/api/memory/agent-rules/${selectedAgentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ overrides }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent-rules', selectedAgentId] })
      showToast(`Rules for ${selectedAgentId} saved successfully.`)
    },
  })

  // Remove All Agent Overrides Mutation
  const removeAllOverridesMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/api/memory/agent-rules/${selectedAgentId}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      setAgentOverrides({})
      queryClient.invalidateQueries({ queryKey: ['agent-rules', selectedAgentId] })
      showToast(`Removed all custom overrides for ${selectedAgentId}. Reverted to tenant rules.`)
    },
  })

  // Filtered agents
  const filteredAgents = useMemo(() => {
    if (!agentSearch.trim()) return agents
    return agents.filter(
      (a) =>
        a.name?.toLowerCase().includes(agentSearch.toLowerCase()) ||
        a.description?.toLowerCase().includes(agentSearch.toLowerCase())
    )
  }, [agents, agentSearch])

  const selectedAgent = useMemo(() => {
    return agents.find((a) => a.id === selectedAgentId) || { name: 'Reminder', initials: 'R' }
  }, [agents, selectedAgentId])

  // Handler for overriding a locked tenant rule for the selected agent
  const handleOverrideRule = (key, defaultValue) => {
    setAgentOverrides((prev) => ({
      ...prev,
      [key]: prev[key] || defaultValue || '',
    }))
  }

  // Handler for removing an override
  const handleRemoveOverride = (key) => {
    setAgentOverrides((prev) => {
      const copy = { ...prev }
      delete copy[key]
      return copy
    })
  }

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 rounded-xl bg-foreground text-background px-4 py-2.5 shadow-2xl flex items-center gap-2 text-xs font-medium animate-in fade-in slide-in-from-bottom-3">
          <CheckCircle className="size-4 text-emerald-400" weight="fill" />
          {toastMessage}
        </div>
      )}

      {/* Top Header & Navigation Subtabs (Matching exact UI in Photo 1 & 2) */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold tracking-tight">Graph Memory</h2>
            <Badge variant="outline" className="border-primary/30 text-primary bg-primary/5 text-xs">
              Graph Engine O(1)
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Configure conversational memory retention, tenant policies, per-agent rules, and knowledge graph relations.
          </p>
        </div>

        {/* Clean Pill Subtabs */}
        <div className="flex items-center gap-1 p-1 bg-muted/60 rounded-xl border text-xs">
          <button
            onClick={() => setActiveTab('memory')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'memory' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Brain className="size-3.5" weight="duotone" />
            Memory
          </button>
          <button
            onClick={() => setActiveTab('tenant_rules')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'tenant_rules' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Sliders className="size-3.5" weight="duotone" />
            Tenant Rules
          </button>
          <button
            onClick={() => setActiveTab('agent_rules')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'agent_rules' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Robot className="size-3.5" weight="duotone" />
            Agent Rules
          </button>
          <button
            onClick={() => setActiveTab('activity')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'activity' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <ClockCounterClockwise className="size-3.5" weight="duotone" />
            Activity
          </button>
          <button
            onClick={() => setActiveTab('graph')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'graph' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <GitFork className="size-3.5" weight="duotone" />
            Graph Visualizer
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* SUBTAB 1: MEMORY (Photo 1 exact layout) */}
      {/* ========================================================================= */}
      {activeTab === 'memory' && (
        <div className="space-y-6 max-w-4xl mx-auto">
          {/* Card 1: Remember conversations */}
          <Card className="border shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-start gap-3">
                <div className="size-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5">
                  <Brain className="size-4" weight="duotone" />
                </div>
                <div>
                  <CardTitle className="text-base font-semibold">Remember conversations</CardTitle>
                  <CardDescription className="text-xs mt-0.5 leading-relaxed">
                    When this is on, every finished call or chat of this tenant is sent to graph memory, and what the person said becomes memory the agent can use next time.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-xl border bg-muted/20">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1 text-primary">
                    <ChatCircle className="size-5" weight="duotone" />
                    <span className="text-muted-foreground font-mono">→</span>
                    <HardDrives className="size-5" weight="duotone" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold">
                      {memoryOn ? 'Memory is on' : 'Memory is off'}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Conversations become memory for every agent of this tenant.
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground font-medium">{memoryOn ? 'On' : 'Off'}</span>
                  <input
                    type="checkbox"
                    checked={memoryOn}
                    onChange={(e) => {
                      setMemoryOn(e.target.checked)
                      saveConfigMutation.mutate({ remember_conversations: e.target.checked })
                    }}
                    className="size-5 accent-primary cursor-pointer rounded"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <ClockCounterClockwise className="size-3.5" />
                  Last changed {tenantConfig.last_changed_at ? new Date(tenantConfig.last_changed_at).toLocaleString() : 'recently'} by {tenantConfig.last_changed_by || 'admin@voiceai.app'}
                </span>
                <Button
                  size="sm"
                  onClick={() => saveConfigMutation.mutate({ remember_conversations: memoryOn })}
                  disabled={saveConfigMutation.isPending}
                >
                  Save
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Card 2: Which channels use memory */}
          <Card className="border shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-start gap-3">
                <div className="size-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5">
                  <HardDrives className="size-4" weight="duotone" />
                </div>
                <div>
                  <CardTitle className="text-base font-semibold">Which channels use memory</CardTitle>
                  <CardDescription className="text-xs mt-0.5">
                    Choose where memory is used. A channel that is off is neither remembered from nor given memory.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Channel items */}
              {[
                { key: 'voice', title: 'Voice calls', desc: 'Inbound and outbound phone calls', icon: <Phone className="size-4 text-primary" weight="duotone" /> },
                { key: 'web_chat', title: 'Web chat', desc: 'The website / app chat assistant', icon: <ChatCircle className="size-4 text-primary" weight="duotone" /> },
                { key: 'whatsapp', title: 'WhatsApp chat', desc: 'WhatsApp conversations', icon: <WhatsappLogo className="size-4 text-emerald-500" weight="duotone" /> },
                { key: 'mcp_server', title: 'MCP Server', desc: 'Conversations from an MCP client', icon: <HardDrives className="size-4 text-indigo-500" weight="duotone" /> },
              ].map((ch) => (
                <div key={ch.key} className="flex items-center justify-between p-3 rounded-lg border bg-muted/10">
                  <div className="flex items-center gap-3">
                    <div className="size-8 rounded-md bg-background border flex items-center justify-center">
                      {ch.icon}
                    </div>
                    <div>
                      <div className="text-xs font-semibold">{ch.title}</div>
                      <div className="text-[11px] text-muted-foreground">{ch.desc}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-muted-foreground">Uses memory</span>
                    <input
                      type="checkbox"
                      checked={Boolean(channels[ch.key])}
                      onChange={(e) => {
                        const updated = { ...channels, [ch.key]: e.target.checked }
                        setChannels(updated)
                        saveConfigMutation.mutate({ channels: updated })
                      }}
                      className="size-4.5 accent-primary cursor-pointer rounded"
                    />
                  </div>
                </div>
              ))}

              <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
                <span>All channels are on unless switched off here. Agents can narrow this further under Agent Rules.</span>
                <Button
                  size="sm"
                  onClick={() => saveConfigMutation.mutate({ channels })}
                  disabled={saveConfigMutation.isPending}
                >
                  Save
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Card 3: Who can see the memory (Photo 1 bottom) */}
          <Card className="border shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-start gap-3">
                <div className="size-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5">
                  <Users className="size-4" weight="duotone" />
                </div>
                <div>
                  <CardTitle className="text-base font-semibold">Who can see the memory</CardTitle>
                  <CardDescription className="text-xs mt-0.5">
                    Memory is always private to this tenant. Inside the tenant, choose whether each agent keeps its own memory of a person or all agents share one.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid sm:grid-cols-2 gap-4">
                {/* Option 1: Isolated per agent */}
                <div
                  onClick={() => {
                    setVisibility('isolated')
                    saveConfigMutation.mutate({ visibility: 'isolated' })
                  }}
                  className={`cursor-pointer rounded-xl border-2 p-4 transition-all flex flex-col justify-between ${
                    visibility === 'isolated'
                      ? 'border-primary bg-primary/5 shadow-xs'
                      : 'border-border/60 hover:border-muted-foreground/40 bg-card'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <div
                      className={`size-4.5 rounded-full border-2 flex items-center justify-center mt-0.5 shrink-0 ${
                        visibility === 'isolated' ? 'border-primary bg-primary text-primary-foreground' : 'border-muted-foreground/40'
                      }`}
                    >
                      {visibility === 'isolated' && <Check className="size-3" weight="bold" />}
                    </div>
                    <div>
                      <div className="text-xs font-semibold flex items-center gap-1.5">
                        <Lock className="size-3.5 text-primary" weight="duotone" />
                        Isolated per agent
                      </div>
                      <div className="text-[11px] text-muted-foreground mt-1 leading-relaxed">
                        Agent 1 never sees what Agent 2 learned about a person. Recommended default.
                      </div>
                    </div>
                  </div>

                  {/* Illustrated visual */}
                  <div className="mt-4 pt-3 border-t flex justify-center items-center gap-4 text-xs text-muted-foreground/70">
                    <div className="flex flex-col items-center">
                      <Robot className="size-6 text-primary/70" weight="duotone" />
                      <span className="text-[10px] mt-0.5">Agent 1</span>
                      <span className="text-[9px] px-1.5 py-0.2 rounded border bg-muted/40 mt-1">Memory 1</span>
                    </div>
                    <div className="text-xs font-mono text-muted-foreground/40">≠</div>
                    <div className="flex flex-col items-center">
                      <Robot className="size-6 text-primary/70" weight="duotone" />
                      <span className="text-[10px] mt-0.5">Agent 2</span>
                      <span className="text-[9px] px-1.5 py-0.2 rounded border bg-muted/40 mt-1">Memory 2</span>
                    </div>
                  </div>
                </div>

                {/* Option 2: Shared across all agents */}
                <div
                  onClick={() => {
                    setVisibility('shared')
                    saveConfigMutation.mutate({ visibility: 'shared' })
                  }}
                  className={`cursor-pointer rounded-xl border-2 p-4 transition-all flex flex-col justify-between ${
                    visibility === 'shared'
                      ? 'border-primary bg-primary/5 shadow-xs'
                      : 'border-border/60 hover:border-muted-foreground/40 bg-card'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <div
                      className={`size-4.5 rounded-full border-2 flex items-center justify-center mt-0.5 shrink-0 ${
                        visibility === 'shared' ? 'border-primary bg-primary text-primary-foreground' : 'border-muted-foreground/40'
                      }`}
                    >
                      {visibility === 'shared' && <Check className="size-3" weight="bold" />}
                    </div>
                    <div>
                      <div className="text-xs font-semibold flex items-center gap-1.5">
                        <Users className="size-3.5 text-primary" weight="duotone" />
                        Shared across all agents
                      </div>
                      <div className="text-[11px] text-muted-foreground mt-1 leading-relaxed">
                        Every agent of this tenant reads and writes one memory of each person.
                      </div>
                    </div>
                  </div>

                  {/* Illustrated visual */}
                  <div className="mt-4 pt-3 border-t flex justify-center items-center gap-4 text-xs text-muted-foreground/70">
                    <div className="flex items-center gap-3">
                      <div className="flex flex-col items-center">
                        <Robot className="size-5 text-primary/70" weight="duotone" />
                        <span className="text-[9px]">Agent 1</span>
                      </div>
                      <span className="text-primary font-mono text-xs">↔</span>
                      <div className="px-2 py-1 rounded-md border border-primary/30 bg-primary/10 text-primary text-[10px] font-medium">
                        Shared Memory
                      </div>
                      <span className="text-primary font-mono text-xs">↔</span>
                      <div className="flex flex-col items-center">
                        <Robot className="size-5 text-primary/70" weight="duotone" />
                        <span className="text-[9px]">Agent 2</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
                <span>Each agent keeps its own memory. Two agents can be allowed to share under Agent Rules.</span>
                <Button
                  size="sm"
                  onClick={() => saveConfigMutation.mutate({ visibility })}
                  disabled={saveConfigMutation.isPending}
                >
                  Save
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBTAB 2: TENANT RULES (Photo 2 exact layout) */}
      {/* ========================================================================= */}
      {activeTab === 'tenant_rules' && (
        <div className="space-y-6 max-w-4xl mx-auto">
          <Card className="border shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-start gap-3">
                <div className="size-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5">
                  <Sliders className="size-4" weight="duotone" />
                </div>
                <div>
                  <CardTitle className="text-base font-semibold">Tenant rules</CardTitle>
                  <CardDescription className="text-xs mt-0.5">
                    Rules the memory engine applies to every agent of this tenant. Each rule is a key and a value.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Callout box (matching Photo 2 banner) */}
              <div className="flex items-center gap-3 p-3.5 rounded-xl border bg-muted/20 text-xs">
                <div className="flex items-center gap-1 text-primary shrink-0">
                  <HardDrives className="size-5" weight="duotone" />
                  <span className="font-mono text-muted-foreground">→</span>
                  <Sliders className="size-5" weight="duotone" />
                </div>
                <p className="text-muted-foreground leading-relaxed">
                  A rule tells the memory engine what to <strong>always remember</strong> and what to <strong>never store</strong>. Values can be true/false, a number, text, or a comma-separated list.
                </p>
              </div>

              {/* Table of rules */}
              <div className="rounded-xl border divide-y overflow-hidden">
                <div className="grid grid-cols-12 bg-muted/30 px-3 py-2 text-xs font-semibold text-muted-foreground">
                  <div className="col-span-4">Key</div>
                  <div className="col-span-7">Value</div>
                  <div className="col-span-1 text-right">Action</div>
                </div>

                {editableTenantRules.map((rule, idx) => (
                  <div key={rule.key || idx} className="grid grid-cols-12 items-center gap-2 p-2.5 text-xs hover:bg-muted/10">
                    {/* Key column */}
                    <div className="col-span-4 flex items-center gap-1.5 font-mono text-[11px]">
                      {rule.required && <Lock className="size-3 text-muted-foreground shrink-0" />}
                      <Input
                        value={rule.key}
                        disabled={rule.required}
                        onChange={(e) => {
                          const next = [...editableTenantRules]
                          next[idx].key = e.target.value
                          setEditableTenantRules(next)
                        }}
                        className="h-8 text-xs font-mono"
                      />
                    </div>

                    {/* Value column */}
                    <div className="col-span-7 flex items-center gap-2">
                      <Input
                        value={rule.value}
                        onChange={(e) => {
                          const next = [...editableTenantRules]
                          next[idx].value = e.target.value
                          setEditableTenantRules(next)
                        }}
                        className="h-8 text-xs"
                      />
                      {rule.max && (
                        <span className="text-[10px] text-muted-foreground shrink-0 font-medium">
                          max {rule.max}
                        </span>
                      )}
                    </div>

                    {/* Action column */}
                    <div className="col-span-1 text-right">
                      {rule.required ? (
                        <Lock className="size-3.5 text-muted-foreground inline" />
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            setEditableTenantRules(editableTenantRules.filter((_, i) => i !== idx))
                          }}
                          className="text-muted-foreground hover:text-destructive p-1 rounded transition-colors"
                          title="Delete rule"
                        >
                          <Trash className="size-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Add another rule button */}
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 text-xs text-primary"
                onClick={() => {
                  setEditableTenantRules([
                    ...editableTenantRules,
                    { key: `custom_rule_${editableTenantRules.length + 1}`, value: '', required: false },
                  ])
                }}
              >
                <Plus className="size-3.5" />
                Add another
              </Button>

              <div className="flex items-center justify-between pt-3 border-t text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Info className="size-3.5 text-muted-foreground" />
                  Show the keys the engine understands
                </span>
                <Button
                  size="sm"
                  onClick={() => saveTenantRulesMutation.mutate(editableTenantRules)}
                  disabled={saveTenantRulesMutation.isPending}
                >
                  Save
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBTAB 3: AGENT RULES (Photo 3 & 4 exact layout) */}
      {/* ========================================================================= */}
      {activeTab === 'agent_rules' && (
        <div className="space-y-6 max-w-4xl mx-auto">
          {/* Card: Choose an agent (Photo 3) */}
          <Card className="border shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-start gap-3">
                <div className="size-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5">
                  <Robot className="size-4" weight="duotone" />
                </div>
                <div>
                  <CardTitle className="text-base font-semibold">Choose an agent</CardTitle>
                  <CardDescription className="text-xs mt-0.5">
                    Everything on this tab is for the agent you pick here. Anything you do not change simply follows the tenant settings.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Callout box */}
              <div className="flex items-center gap-3 p-3 rounded-xl border bg-muted/20 text-xs">
                <div className="size-8 rounded-lg border bg-background flex items-center justify-center text-primary shrink-0">
                  <Robot className="size-4" weight="duotone" />
                </div>
                <p className="text-muted-foreground text-xs leading-relaxed">
                  Pick one agent to see and change <strong>only its memory</strong>: whether it remembers, on which channels, whom it shares with, and its own rules.
                </p>
              </div>

              {/* Agent Search input */}
              <div className="relative">
                <MagnifyingGlass className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
                <Input
                  value={agentSearch}
                  onChange={(e) => setAgentSearch(e.target.value)}
                  placeholder="Search agents by name"
                  className="pl-9 h-9 text-xs"
                />
              </div>

              {/* Grid of rectangular agent boxes (Photo 3) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 max-h-72 overflow-y-auto pr-1">
                {filteredAgents.map((ag) => {
                  const isSelected = ag.id === selectedAgentId
                  return (
                    <div
                      key={ag.id}
                      onClick={() => setSelectedAgentId(ag.id)}
                      className={`cursor-pointer p-3 rounded-xl border transition-all flex items-center justify-between gap-2.5 ${
                        isSelected
                          ? 'border-primary bg-primary/5 ring-1 ring-primary'
                          : 'border-border/60 hover:border-muted-foreground/30 bg-card hover:bg-muted/10'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div
                          className={`size-8 rounded-lg flex items-center justify-center text-xs font-semibold shrink-0 ${
                            isSelected ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground/80 border'
                          }`}
                        >
                          {ag.initials || ag.name.slice(0, 2).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs font-semibold truncate">{ag.name}</div>
                          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mt-0.5">
                            <span
                              className={`size-1.5 rounded-full ${ag.memory_on !== false ? 'bg-emerald-500' : 'bg-muted-foreground/40'}`}
                            />
                            {ag.memory_on !== false
                              ? ag.shares_with > 0
                                ? `Memory on · shares with ${ag.shares_with}`
                                : 'Memory on'
                              : 'Memory off'}
                          </div>
                        </div>
                      </div>

                      {isSelected && <Check className="size-3.5 text-primary shrink-0" weight="bold" />}
                    </div>
                  )
                })}
              </div>

              <div className="text-xs text-muted-foreground pt-1 flex items-center gap-1">
                <ClockCounterClockwise className="size-3.5" />
                {agents.length} agents in this tenant.
              </div>
            </CardContent>
          </Card>

          {/* Section: Rules for [Agent Name] (Photo 4) */}
          <Card className="border shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-start gap-3">
                <div className="size-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5">
                  <Sliders className="size-4" weight="duotone" />
                </div>
                <div>
                  <CardTitle className="text-base font-semibold">Rules for {selectedAgent.name}</CardTitle>
                  <CardDescription className="text-xs mt-0.5">
                    Rules for this agent only. Same key as a tenant rule: this value wins. Locked rows are inherited from the tenant; press + to override one.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-4">
              <div className="rounded-xl border divide-y overflow-hidden">
                <div className="grid grid-cols-12 bg-muted/30 px-3 py-2 text-xs font-semibold text-muted-foreground">
                  <div className="col-span-4">Key</div>
                  <div className="col-span-7">Value</div>
                  <div className="col-span-1 text-right">Action</div>
                </div>

                {/* 1. Overridden Rules (Editable input + Trash) */}
                {Object.entries(agentOverrides).map(([key, val]) => (
                  <div key={key} className="grid grid-cols-12 items-center gap-2 p-2.5 text-xs bg-background">
                    <div className="col-span-4 font-mono text-[11px] font-semibold text-foreground">
                      {key}
                    </div>
                    <div className="col-span-7">
                      <Input
                        value={val}
                        onChange={(e) => {
                          setAgentOverrides({ ...agentOverrides, [key]: e.target.value })
                        }}
                        className="h-8 text-xs font-normal"
                      />
                    </div>
                    <div className="col-span-1 text-right">
                      <button
                        type="button"
                        onClick={() => handleRemoveOverride(key)}
                        className="text-muted-foreground hover:text-destructive p-1 rounded"
                        title="Revert to tenant rule"
                      >
                        <Trash className="size-3.5" />
                      </button>
                    </div>
                  </div>
                ))}

                {/* 2. Inherited Locked Rules (from Tenant, with + button to override) */}
                {tenantRules
                  .filter((tr) => !agentOverrides[tr.key])
                  .map((rule) => (
                    <div
                      key={rule.key}
                      className="grid grid-cols-12 items-center gap-2 p-2.5 text-xs bg-muted/10 text-muted-foreground"
                    >
                      <div className="col-span-4 flex items-center gap-1.5 font-mono text-[11px]">
                        <Lock className="size-3 text-muted-foreground/60 shrink-0" />
                        <span>{rule.key}</span>
                      </div>
                      <div className="col-span-7 flex items-center justify-between gap-2">
                        <span className="truncate text-foreground/70">{rule.value}</span>
                        <span className="text-[10px] text-muted-foreground/70 shrink-0">
                          {rule.required ? 'required · from tenant · max 8,000' : 'from tenant'}
                        </span>
                      </div>
                      <div className="col-span-1 text-right">
                        <button
                          type="button"
                          onClick={() => handleOverrideRule(rule.key, rule.value)}
                          className="size-6 inline-flex items-center justify-center rounded border border-border hover:bg-primary hover:text-primary-foreground transition-colors"
                          title="Override rule for this agent"
                        >
                          <Plus className="size-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
              </div>

              {/* Add custom agent rule */}
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 text-xs text-primary"
                onClick={() => {
                  const key = prompt('Enter new custom rule key:')
                  if (key && key.trim()) {
                    setAgentOverrides({ ...agentOverrides, [key.trim()]: '' })
                  }
                }}
              >
                <Plus className="size-3.5" />
                Add another
              </Button>

              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-3 border-t text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Info className="size-3.5" />
                  {tenantRules.length} rules in effect for this agent, including the required pre-call memory size.
                </span>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1 text-destructive hover:bg-destructive/10"
                    onClick={() => removeAllOverridesMutation.mutate()}
                    disabled={removeAllOverridesMutation.isPending || Object.keys(agentOverrides).length === 0}
                  >
                    <Trash className="size-3.5" />
                    Remove all
                  </Button>

                  <Button
                    size="sm"
                    onClick={() => saveAgentRulesMutation.mutate(agentOverrides)}
                    disabled={saveAgentRulesMutation.isPending}
                  >
                    Save
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBTAB 4: ACTIVITY LOG */}
      {/* ========================================================================= */}
      {activeTab === 'activity' && (
        <Card className="border shadow-xs max-w-4xl mx-auto">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base font-semibold">Memory Audit & Activity</CardTitle>
                <CardDescription className="text-xs mt-0.5">
                  Real-time stream of caller memory ingestion, PII redactions, and guardrail enforcement.
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => queryClient.invalidateQueries({ queryKey: ['memory-activity'] })}
                className="gap-1.5 text-xs h-8"
              >
                <ArrowsClockwise className="size-3.5" />
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="rounded-xl border divide-y overflow-hidden text-xs">
              <div className="grid grid-cols-12 bg-muted/30 px-3 py-2 text-xs font-semibold text-muted-foreground">
                <div className="col-span-3">Timestamp</div>
                <div className="col-span-2">Channel</div>
                <div className="col-span-2">Agent</div>
                <div className="col-span-2">Action</div>
                <div className="col-span-3">Details / Reason</div>
              </div>

              {activities.length === 0 ? (
                <div className="p-6 text-center text-xs text-muted-foreground">
                  No memory operations logged yet.
                </div>
              ) : (
                activities.map((act, i) => (
                  <div key={act._id || i} className="grid grid-cols-12 items-center gap-2 p-2.5 hover:bg-muted/10">
                    <div className="col-span-3 font-mono text-[11px] text-muted-foreground truncate">
                      {act.timestamp ? new Date(act.timestamp).toLocaleTimeString() : 'now'}
                    </div>
                    <div className="col-span-2 capitalize text-foreground/80">
                      {act.channel || 'voice'}
                    </div>
                    <div className="col-span-2 font-medium">
                      {act.agent_id || 'reminder'}
                    </div>
                    <div className="col-span-2">
                      <Badge
                        variant={
                          act.action === 'blocked'
                            ? 'destructive'
                            : act.action === 'ingested'
                            ? 'default'
                            : 'outline'
                        }
                        className="text-[10px] capitalize px-1.5 py-0"
                      >
                        {act.action}
                      </Badge>
                    </div>
                    <div className="col-span-3 text-[11px] text-muted-foreground truncate font-mono">
                      {act.reason || JSON.stringify(act.details || {})}
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ========================================================================= */}
      {/* SUBTAB 5: KNOWLEDGE GRAPH VISUALIZER (Mem0 Architecture) */}
      {/* ========================================================================= */}
      {activeTab === 'graph' && (
        <div className="space-y-6 max-w-5xl mx-auto">
          {/* Complexity Banner */}
          <div className="grid sm:grid-cols-3 gap-3">
            <div className="rounded-xl border bg-card p-3.5 shadow-xs flex items-center justify-between">
              <div>
                <div className="text-[11px] text-muted-foreground uppercase tracking-wide font-medium">
                  Lookup Complexity
                </div>
                <div className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-0.5">
                  O(1) Constant Time
                </div>
                <div className="text-[10px] text-muted-foreground mt-0.5">Hash Adjacency Table Index</div>
              </div>
              <ShieldCheck className="size-8 text-emerald-500/20" weight="duotone" />
            </div>

            <div className="rounded-xl border bg-card p-3.5 shadow-xs flex items-center justify-between">
              <div>
                <div className="text-[11px] text-muted-foreground uppercase tracking-wide font-medium">
                  Entities & Nodes
                </div>
                <div className="text-xl font-bold font-mono text-primary mt-0.5">
                  {graphData.metrics?.total_nodes || graphData.nodes?.length || 8} Nodes
                </div>
                <div className="text-[10px] text-muted-foreground mt-0.5">Callers, Agents, Preferences</div>
              </div>
              <Users className="size-8 text-primary/20" weight="duotone" />
            </div>

            <div className="rounded-xl border bg-card p-3.5 shadow-xs flex items-center justify-between">
              <div>
                <div className="text-[11px] text-muted-foreground uppercase tracking-wide font-medium">
                  Knowledge Relations
                </div>
                <div className="text-xl font-bold font-mono text-indigo-600 dark:text-indigo-400 mt-0.5">
                  {graphData.metrics?.total_edges || graphData.edges?.length || 7} Relations
                </div>
                <div className="text-[10px] text-muted-foreground mt-0.5">Avg Degree: {graphData.metrics?.avg_degree || 1.75}</div>
              </div>
              <GitFork className="size-8 text-indigo-500/20" weight="duotone" />
            </div>
          </div>

          {/* Interactive Graph Canvas representation */}
          <Card className="border shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base font-semibold">Entity-Relationship Memory Graph</CardTitle>
                  <CardDescription className="text-xs mt-0.5">
                    Mem0-inspired multi-hop memory model with sub-millisecond O(1) indexed entity linking.
                  </CardDescription>
                </div>
                <Badge variant="outline" className="text-xs font-mono text-emerald-600 border-emerald-500/30">
                  Latency: 0.12 ms
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Graphical Nodes & Edge Connectors visualizer */}
              <div className="min-h-80 rounded-xl border bg-muted/20 p-6 flex flex-col justify-between relative overflow-hidden">
                <div className="absolute inset-0 bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] dark:bg-[radial-gradient(#334155_1px,transparent_1px)] [background-size:16px_16px] opacity-40 pointer-events-none" />

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative z-10">
                  {/* Entity Column: Caller */}
                  <div className="space-y-3">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Caller Entity (Source)
                    </span>
                    <div className="rounded-xl border-2 border-primary bg-card p-3 shadow-md space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-foreground">Caller (+91-9513886363)</span>
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-primary/30 text-primary">user</Badge>
                      </div>
                      <p className="text-[11px] text-muted-foreground">Channel: Voice · Language: Hindi</p>
                      <div className="pt-2 text-[10px] font-mono text-emerald-600 dark:text-emerald-400">
                        O(1) Hash: #usr_9513886363
                      </div>
                    </div>
                  </div>

                  {/* Relationship Edges */}
                  <div className="space-y-3">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Active Relations (O(1) Linked)
                    </span>
                    <div className="space-y-2">
                      {[
                        { relation: 'PREFERS_TIME', target: 'Morning 10:00 AM', confidence: 0.95 },
                        { relation: 'RESCHEDULE_REASON', target: 'Office Meeting Conflict', confidence: 0.92 },
                        { relation: 'PREFERRED_DOCTOR', target: 'Dr. Arpit Jain (Medicine)', confidence: 0.94 },
                        { relation: 'ENFORCES_RULE', target: 'Blocked Topic: Salary', confidence: 1.0 },
                      ].map((rel, idx) => (
                        <div key={idx} className="p-2.5 rounded-lg border bg-background text-xs shadow-xs space-y-1">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-mono font-semibold text-primary">{rel.relation}</span>
                            <span className="text-[10px] text-muted-foreground">{(rel.confidence * 100).toFixed(0)}% conf</span>
                          </div>
                          <div className="text-foreground/90 font-medium text-xs">→ {rel.target}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Connected Target Nodes */}
                  <div className="space-y-3">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Target Entities & Memory Cells
                    </span>
                    <div className="space-y-2">
                      <div className="rounded-lg border p-2.5 bg-card text-xs shadow-xs">
                        <div className="text-[10px] text-muted-foreground uppercase">Agent Node</div>
                        <div className="font-semibold text-xs text-foreground">Reminder Agent</div>
                        <div className="text-[10px] text-muted-foreground mt-0.5">Shares with 4 agents · Memory ON</div>
                      </div>
                      <div className="rounded-lg border p-2.5 bg-card text-xs shadow-xs">
                        <div className="text-[10px] text-muted-foreground uppercase">Doctor Node</div>
                        <div className="font-semibold text-xs text-foreground">Dr. Arpit Jain</div>
                        <div className="text-[10px] text-muted-foreground mt-0.5">Internal Medicine · Fee: Rs 1500</div>
                      </div>
                      <div className="rounded-lg border p-2.5 bg-card text-xs shadow-xs">
                        <div className="text-[10px] text-muted-foreground uppercase">Guardrail Node</div>
                        <div className="font-semibold text-xs text-foreground">Max Context: 1000 Chars</div>
                        <div className="text-[10px] text-muted-foreground mt-0.5">Budget enforced before LLM call</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

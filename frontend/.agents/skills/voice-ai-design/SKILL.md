---
name: voice-ai-design
description: >-
  Design system and UI guidelines for the Voice AI frontend. Covers the tech stack
  (React + Vite + TailwindCSS v4 + shadcn/ui + Phosphor Icons duotone), color palette,
  typography, component patterns, animation conventions, and the Orb integration.
  Activate when creating or refining any UI component, page, or visual element in this project.
---

# Voice AI Frontend — Design Skill

## Stack

| Layer | Tool |
|---|---|
| Framework | React 19 + Vite 8 |
| Styling | TailwindCSS v4 (via `@tailwindcss/vite`) |
| Component library | shadcn/ui (Radix primitives) |
| Icons | `@phosphor-icons/react` — **always `weight="duotone"`** |
| 3D / Orb | `@react-three/fiber` + `@react-three/drei` + Three.js |
| Routing | `react-router-dom` v7 |
| Data fetching | `@tanstack/react-query` v5 |

---

## File Locations

```
frontend/src/
├── App.jsx                  # All page components + routes
├── index.css                # Global design tokens & base styles
├── components/
│   ├── app-shell.jsx        # Page wrapper (header + content area)
│   ├── app-sidebar.jsx      # Sidebar nav (navigation array lives here)
│   ├── nav-main.jsx         # Renders sidebar nav items
│   ├── theme-toggle.jsx     # Light / dark / system switcher
│   └── ui/
│       ├── orb.jsx          # ElevenLabs 3D animated orb (WebGL)
│       ├── sidebar.jsx      # Full sidebar primitive system
│       ├── button.jsx
│       ├── card.jsx
│       ├── badge.jsx
│       ├── input.jsx
│       ├── label.jsx
│       ├── table.jsx
│       └── ...              # Other shadcn/ui primitives
├── hooks/
│   └── use-mobile.jsx
└── lib/
    └── utils.js             # cn() helper
```

---

## Design Tokens & Color Palette

The project uses CSS variables set in `index.css` with TailwindCSS v4 `@theme`.
All colors are HSL-based and automatically switch in dark mode.

### Key semantic tokens

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--background` | white | dark slate | Page background |
| `--foreground` | near-black | near-white | Body text |
| `--primary` | indigo-ish | indigo | Buttons, active states |
| `--muted` | light gray | dark gray | Backgrounds, disabled |
| `--sidebar` | slightly off-white | dark | Sidebar surface |
| `--sidebar-accent` | light indigo | dark indigo | Sidebar hover/active |
| `--card` | white | dark card | Card surfaces |
| `--border` | light gray | dark gray | Borders, dividers |

### Orb accent colors

The Orb uses an indigo–violet gradient:
```jsx
colors={["#818cf8", "#c4b5fd"]}
```
Matches Tailwind's `indigo-400` and `violet-300`.

---

## Typography

- **Font**: System font stack via TailwindCSS (no Google Fonts currently)
- **Page titles**: `text-2xl font-semibold tracking-tight` (via `PageIntro`)
- **Card titles**: `CardTitle` component
- **Descriptions**: `text-muted-foreground text-sm`
- **Labels**: `text-xs font-medium` uppercase for status indicators
- **Sidebar brand**: `text-base font-semibold tracking-wide`

---

## Icons — Phosphor Duotone

**Rule: All Phosphor icons MUST use `weight="duotone"`.**

```jsx
import { ChartBar, PhoneCall, Waveform } from '@phosphor-icons/react'

// Always:
<ChartBar weight="duotone" />

// Never:
<ChartBar />  // defaults to "regular" — not allowed
```

### Sidebar nav icons

| Route | Icon |
|---|---|
| `/overview` | `ChartBar` |
| `/interactions` | `PhoneCall` |
| `/bookings` | `CalendarCheck` |
| `/agent` | `Robot` |

### In-app usage

| Location | Icon |
|---|---|
| Orb upload button | `UploadSimple` |
| Status list rows | `Waveform` |
| Theme toggle | `Sun`, `Moon`, `Desktop` |
| Sidebar trigger | `List` |
| Overview card | `Pulse` |
| Sidebar logo | `Waveform` (bold weight as brand mark) |

---

## Page Layout Pattern

Every page follows this structure:

```jsx
<AppShell title="Page Title">
  <PageIntro
    title="Human-readable heading"
    lede="One sentence describing what this page shows."
    meta={isLoading ? 'Loading' : 'Live data'}
  />

  {/* Page content — grids, cards, tables */}
</AppShell>
```

**Grid system**: Use `grid gap-4 lg:grid-cols-12` with `lg:col-span-N` for responsive layouts.

---

## Component Conventions

### Cards

```jsx
// Data card (tables, lists)
<Card>
  <CardContent className="px-0">
    <Table>...</Table>
  </CardContent>
</Card>

// Info/control card
<Card className="bg-muted/40 lg:col-span-4">
  <CardContent className="flex flex-col gap-4">
    ...
  </CardContent>
</Card>
```

### Badges

| Variant | When to use |
|---|---|
| `success` | Positive sentiment |
| `destructive` | Negative sentiment |
| `secondary` | Neutral sentiment |
| `outline` | Tool names, meta info |

### Buttons

```jsx
// Primary action
<Button type="button">
  <IconName size={18} weight="duotone" /> Label
</Button>

// Secondary action
<Button type="button" variant="outline">
  <IconName size={18} weight="duotone" /> Label
</Button>
```

---

## The Orb Component

Located at `@/components/ui/orb.jsx`.

### Props

| Prop | Type | Default | Purpose |
|---|---|---|---|
| `agentState` | `null \| "thinking" \| "listening" \| "talking"` | `null` | Controls orb animation mode |
| `colors` | `[string, string]` | `["#CADCFC","#A0B9D1"]` | Gradient colors |
| `getInputVolume` | `() => number` (0–1) | — | Live mic volume feed |
| `getOutputVolume` | `() => number` (0–1) | — | Live speaker volume feed |
| `volumeMode` | `"auto" \| "manual"` | `"auto"` | Use built-in simulation or manual values |
| `className` | string | `"relative h-full w-full"` | Container class |

### Agent state → Orb behaviour

| Status | agentState | Orb animation |
|---|---|---|
| `recording` | `"listening"` | Pulses with mic input, waves actively |
| `processing` | `"thinking"` | Slow steady wander |
| `playing` | `"talking"` | Strong output-driven waves |
| anything else | `null` | Gentle idle float |

### Standard usage (Agent Console)

```jsx
<div
  className="relative cursor-pointer select-none"
  style={{ width: 180, height: 180 }}
  onMouseDown={isRecording ? stopRecording : startRecording}
  onTouchStart={(e) => { e.preventDefault(); isRecording ? stopRecording() : startRecording() }}
>
  <Orb
    agentState={agentState}
    getInputVolume={getInputVolume}
    colors={["#818cf8", "#c4b5fd"]}
    className="h-full w-full"
  />
</div>
<p className="text-xs text-muted-foreground font-medium tracking-wide uppercase">
  {orbLabel}
</p>
```

### Live mic volume with Web Audio API

```jsx
const analyserRef = useRef(null)
const audioDataRef = useRef(null)

const getInputVolume = useCallback(() => {
  const analyser = analyserRef.current
  if (!analyser) return 0
  analyser.getByteFrequencyData(audioDataRef.current)
  const sum = audioDataRef.current.reduce((a, b) => a + b, 0)
  return Math.min(1, sum / (audioDataRef.current.length * 128))
}, [])

// When starting recording:
const audioCtx = new AudioContext()
const source = audioCtx.createMediaStreamSource(stream)
const analyser = audioCtx.createAnalyser()
analyser.fftSize = 256
source.connect(analyser)
analyserRef.current = analyser
audioDataRef.current = new Uint8Array(analyser.frequencyBinCount)
```

---

## Animation Conventions

- **No CSS `animate-ping`** — removed as it conflicts with the Orb's own animations
- **Transitions**: Use TailwindCSS `transition-*` utilities for interactive states
- **Hover effects**: `hover:bg-sidebar-accent hover:text-sidebar-accent-foreground`
- **Active nav**: `data-[active=true]:bg-sidebar-accent data-[active=true]:font-medium`
- **Dark mode**: Handled via `document.documentElement.classList.contains("dark")` + MutationObserver

---

## Sidebar Navigation

To add a new route to the sidebar, edit `app-sidebar.jsx`:

```jsx
import { NewIcon } from '@phosphor-icons/react'

const navigation = [
  // ... existing items
  { title: 'New Page', url: '/new-page', icon: <NewIcon weight="duotone" /> },
]
```

Then add the route in `App.jsx`:
```jsx
<Route path="/new-page" element={<NewPage />} />
```

---

## Do's and Don'ts

### ✅ Do
- Use `weight="duotone"` on every Phosphor icon
- Use `cn()` from `@/lib/utils` for conditional classNames
- Follow the `AppShell > PageIntro > content` page structure
- Use semantic CSS variables (`text-muted-foreground`, `bg-muted/40`, etc.)
- Map WebSocket/API status → Orb `agentState` explicitly
- Keep page components in `App.jsx` alongside their data-fetching logic

### ❌ Don't
- Use raw color values (e.g. `text-blue-500`) — prefer semantic tokens
- Add `animate-ping` overlays on the Orb
- Use plain `<img>` for icons — use Phosphor React components
- Forget `transparent={true}` on the Orb's shaderMaterial
- Skip `aria-live="polite"` on status output regions

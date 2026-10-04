import { Link, useLocation } from 'react-router-dom'
import {
  ChartBar,
  PhoneCall,
  Robot,
  Waveform,
  MagnifyingGlass,
  ShieldCheck,
  Coins,
  Brain,
  Microphone,
  GearSix,
  CalendarBlank,
} from '@phosphor-icons/react'

import { NavMain } from '@/components/nav-main'
import { ThemeToggle } from '@/components/theme-toggle'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from '@/components/ui/sidebar'

const navigation = [
  { title: 'Overview', url: '/overview', icon: <ChartBar weight="duotone" /> },
  { title: 'Agents', url: '/agents', icon: <Robot weight="duotone" /> },
  { title: 'Agent Config', url: '/agent-config', icon: <GearSix weight="duotone" /> },
  { title: 'Memory', url: '/memory', icon: <Brain weight="duotone" /> },
  { title: 'Interactions', url: '/interactions', icon: <PhoneCall weight="duotone" /> },
  { title: 'Bookings', url: '/bookings', icon: <CalendarBlank weight="duotone" /> },
  { title: 'RAG Inspector', url: '/rag', icon: <MagnifyingGlass weight="duotone" /> },
  { title: 'Safety & Guardrails', url: '/safety', icon: <ShieldCheck weight="duotone" /> },
  { title: 'Token Metrics', url: '/tokens', icon: <Coins weight="duotone" /> },
  { title: 'Agent Console', url: '/agent', icon: <Microphone weight="duotone" /> },
]

export function AppSidebar({ ...props }) {
  const location = useLocation()

  return (
    <Sidebar collapsible="offcanvas" className="border-r" {...props}>
      <SidebarHeader className="px-4 pt-5 pb-3">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              className="px-1 data-[slot=sidebar-menu-button]:p-1!"
              asChild
            >
              <Link to="/overview">
                <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
                  <Waveform className="size-4" weight="duotone" />
                </span>
                <span className="text-base font-semibold tracking-wide">Voice AI</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent className="px-2">
        <SidebarGroup>
          <SidebarGroupLabel>Console</SidebarGroupLabel>
          <NavMain items={navigation} activePath={location.pathname} />
        </SidebarGroup>
      </SidebarContent>

      <SidebarSeparator className="mx-2" />

      <SidebarFooter className="gap-2 p-3">
        <div className="flex items-center justify-between gap-2 rounded-md border border-sidebar-border bg-background/60 px-2 py-1.5">
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">Operational console</span>
            <span className="block truncate text-xs text-muted-foreground">Live backend data</span>
          </span>
          <ThemeToggle className="size-8" />
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}

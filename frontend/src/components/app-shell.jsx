import { useEffect } from 'react'

import { AppSidebar } from '@/components/app-sidebar'
import { SiteHeader } from '@/components/site-header'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'

export function AppShell({ title, children }) {
  useEffect(() => {
    document.title = `${title} · Voice AI`
  }, [title])

  return (
    <TooltipProvider delayDuration={200}>
      <SidebarProvider
        style={{
          '--sidebar-width': 'calc(var(--spacing, 0.25rem) * 76)',
          '--header-height': 'calc(var(--spacing, 0.25rem) * 14)',
        }}
      >
        <AppSidebar />
        <SidebarInset>
          <SiteHeader title={title} />
          <main className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col gap-5 px-4 py-5 md:gap-6 md:px-8 md:py-8 xl:px-10">
            {children}
          </main>
        </SidebarInset>
      </SidebarProvider>
    </TooltipProvider>
  )
}

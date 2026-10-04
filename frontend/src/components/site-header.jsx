import { SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SignOut, ShieldCheck } from '@phosphor-icons/react'

export function SiteHeader({ title }) {
  const username = (typeof window !== 'undefined' && window.localStorage?.getItem('voice_ai_username')) || 'admin'

  const handleLogout = () => {
    window.localStorage?.removeItem('voice_ai_admin_token')
    window.localStorage?.removeItem('voice_ai_username')
    window.location.reload()
  }

  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b bg-background/80 backdrop-blur-sm transition-[width,height] ease-linear">
      <div className="flex w-full items-center justify-between px-4 lg:px-6">
        <div className="flex items-center gap-2">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mx-2 h-4" />
          <h1 className="text-base font-semibold">{title}</h1>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="outline" className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 text-xs text-muted-foreground border-emerald-500/30 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400">
            <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Tenant: default
          </Badge>

          <div className="flex items-center gap-2 text-xs">
            <span className="hidden md:inline-flex items-center gap-1 font-medium text-foreground/80">
              <ShieldCheck className="size-3.5 text-primary" weight="duotone" />
              {username}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
              title="Sign out"
            >
              <SignOut className="size-3.5" />
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </div>
      </div>
    </header>
  )
}


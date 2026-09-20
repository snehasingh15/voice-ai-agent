import { SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'

export function SiteHeader({ title }) {
  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b bg-background/80 backdrop-blur-sm transition-[width,height] ease-linear">
      <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mx-2 h-4" />
        <h1 className="text-base font-medium">{title}</h1>
      </div>
    </header>
  )
}

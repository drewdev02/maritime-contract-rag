import { Link } from "@tanstack/react-router"
import {
  Anchor,
  UploadCloud,
  FileSpreadsheet,
  MessageSquare,
} from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/shared/components/ui/sidebar"

const NAV_ITEMS = [
  { to: "/upload", label: "Ingesta de Pólizas", icon: UploadCloud },
  { to: "/documents", label: "Registro de Pólizas", icon: FileSpreadsheet },
  { to: "/chat", label: "Auditoría RAG", icon: MessageSquare },
] as const

export function AppSidebar() {
  return (
    <Sidebar
      collapsible="none"
      className="sticky top-0 z-20 h-screen shrink-0 border-r border-sidebar-border select-none"
    >
      {/* 1. Cabecera Institucional del Armador */}
      <SidebarHeader className="h-14 flex-row items-center gap-3 border-b border-sidebar-border px-4 py-0">
        <div className="p-2 bg-sidebar-primary text-sidebar-primary-foreground rounded-md flex items-center justify-center shrink-0 shadow-xs">
          <Anchor className="w-4 h-4 stroke-[2.5]" />
        </div>
        <div className="flex flex-col overflow-hidden">
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-xs tracking-tight text-sidebar-foreground truncate">
              Naviera Portecho
            </span>
            <span className="text-[9px] font-mono uppercase bg-teal-500/10 text-teal-400 border border-teal-500/20 px-1 py-0.2 rounded font-semibold">
              RAG
            </span>
          </div>
          <span className="text-[10px] text-slate-400 font-mono leading-tight truncate">
            Despacho y Pólizas
          </span>
        </div>
      </SidebarHeader>

      <SidebarContent className="px-3 py-4 gap-6">
        {/* 2. Menú de Navegación Principal */}
        <SidebarGroup className="p-0">
          <SidebarGroupLabel className="h-auto px-2 mb-2 text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
            Módulos Operativos
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1.5">
              {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                <SidebarMenuItem key={to}>
                  <SidebarMenuButton
                    asChild
                    className="h-auto gap-3 px-3 py-2 text-xs font-medium text-slate-300 hover:text-white data-[active=true]:border-l-2 data-[active=true]:border-sidebar-primary data-[active=true]:font-semibold data-[active=true]:text-white"
                  >
                    <Link to={to} activeProps={{ "data-active": "true" }}>
                      <Icon className="w-4 h-4 shrink-0 text-slate-400" />
                      <span>{label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

      </SidebarContent>

    </Sidebar>
  )
}

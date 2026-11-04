import { createRootRoute, Outlet, useRouterState } from "@tanstack/react-router";
import { useDocumentEvents } from "@/features/documents/api/useDocumentEvents";
import { AppSidebar } from "@/shared/components/AppSidebar";
import { SidebarInset, SidebarProvider } from "@/shared/components/ui/sidebar";
import { Toaster } from "@/shared/components/ui/sonner";

export const Route = createRootRoute({
  component: RootLayout,
});

function RootLayout() {
  useDocumentEvents();
  const isChat = useRouterState({ select: (s) => s.location.pathname.startsWith("/chat") });
  return (
    <SidebarProvider className="min-h-screen bg-[#070D15] text-slate-100 font-sans antialiased">
      {/* 1. Sidebar Fijo de Navegación Lateral (Naviera Portecho) */}
      <AppSidebar />

      {/* 2. Área de Trabajo Principal */}
      <SidebarInset className="flex-1 flex flex-col min-w-0 bg-[#070D15]">
        {/* Barra Superior Técnica de la Consola */}
        <header className="h-14 border-b border-slate-800 bg-[#0B131E]/90 backdrop-blur flex items-center px-6 sticky top-0 z-10 shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
              Terminal de Operaciones
            </span>
            <span className="text-slate-600 font-mono">/</span>
            <span className="text-xs font-mono text-slate-200 font-medium">
              Auditoría Legal de Fletamentos RAG
            </span>
          </div>
        </header>

        {/* Contenido Dinámico de la Ruta */}
        <main
          className={
            isChat
              ? "flex-1 w-full min-h-0 flex flex-col"
              : "flex-1 max-w-6xl w-full mx-auto p-6 flex flex-col"
          }
        >
          <Outlet />
        </main>
      </SidebarInset>

      <Toaster position="top-right" richColors closeButton />
    </SidebarProvider>
  );
}

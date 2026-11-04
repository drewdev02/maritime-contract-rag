import { useState, useMemo } from "react";
import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { z } from "zod";
import { UploadCloud, RefreshCw } from "lucide-react";
import { DocumentStatus } from "@/features/documents/types/document.types";
import { useDocuments } from "@/features/documents/api/useDocuments";
import { DocumentTable } from "@/features/documents/components/DocumentTable";
import { DocumentFilterBar } from "@/features/documents/components/DocumentFilterBar";
import { Button } from "@/shared/components/ui/button";

const documentsSearchSchema = z.object({
  status: z.nativeEnum(DocumentStatus).optional(),
  search: z.string().optional(),
});

export const Route = createFileRoute("/documents")({
  validateSearch: (search) => documentsSearchSchema.parse(search),
  component: DocumentsPage,
});

function DocumentsPage() {
  const searchParams = Route.useSearch();
  const navigate = useNavigate();
  const [localSearch, setLocalSearch] = useState(searchParams.search || "");

  const {
    data: documents = [],
    isLoading,
    isFetching,
    refetch,
  } = useDocuments({
    status: searchParams.status,
  });

  const handleStatusChange = (newStatus: DocumentStatus | undefined) => {
    navigate({
      to: "/documents",
      search: {
        status: newStatus,
        search: searchParams.search,
      },
    });
  };

  const handleSearchChange = (query: string) => {
    setLocalSearch(query);
    navigate({
      to: "/documents",
      search: {
        status: searchParams.status,
        search: query ? query : undefined,
      },
    });
  };

  // Filtrado de documentos por nombre de archivo
  const filteredDocuments = useMemo(() => {
    if (!localSearch.trim()) return documents;
    const q = localSearch.toLowerCase();
    return documents.filter((doc) => doc.filename.toLowerCase().includes(q));
  }, [documents, localSearch]);

  const hasActiveWork = useMemo(() => {
    return documents.some(
      (doc) => doc.status === DocumentStatus.PENDING || doc.status === DocumentStatus.PROCESSING
    );
  }, [documents]);

  const totalChunks = useMemo(() => {
    return documents.reduce((acc, doc) => acc + (doc.chunk_count || 0), 0);
  }, [documents]);

  return (
    <div className="flex flex-col gap-5 max-w-6xl mx-auto py-2">
      {/* Encabezado de la página */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-white">
              Catálogo de Contratos
            </h2>
            {isFetching && !isLoading && (
              <RefreshCw className="w-3.5 h-3.5 text-slate-400 animate-spin" />
            )}
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-teal-400 border border-slate-700 font-semibold">
              {documents.length} PÓLIZAS / {totalChunks} CHUNKS
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Inventario de acuerdos marítimos indexados en la base de conocimiento vectorial de Naviera Portecho.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-xs h-8 gap-1.5 border-slate-800 bg-[#0B131E] hover:bg-slate-800 text-slate-300 hover:text-white rounded"
            title="Refrescar lista"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin" : ""}`} />
            <span>Refrescar</span>
          </Button>

          <Button asChild size="sm" variant="default" className="text-xs h-8 gap-1.5 bg-teal-500 hover:bg-teal-400 text-slate-950 font-semibold rounded shadow-xs border border-teal-400">
            <Link to="/upload">
              <UploadCloud className="w-3.5 h-3.5" />
              <span>Subir Contrato</span>
            </Link>
          </Button>
        </div>
      </div>

      {/* Indicador de polling activo si hay contratos procesándose */}
      {hasActiveWork && (
        <div
          data-testid="active-polling-indicator"
          className="flex items-center gap-2 px-3 py-2 bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800 text-sky-800 dark:text-sky-300 rounded text-xs font-mono"
        >
          <RefreshCw className="w-3.5 h-3.5 animate-spin shrink-0 text-sky-600" />
          <span>
            SINCRONIZACIÓN EN TIEMPO REAL ACTIVA (2s): Extrayendo tablas y vectorizando en segundo plano.
          </span>
        </div>
      )}

      {/* Barra de filtros y búsqueda */}
      <DocumentFilterBar
        currentStatus={searchParams.status}
        searchQuery={localSearch}
        onStatusChange={handleStatusChange}
        onSearchChange={handleSearchChange}
        totalCount={filteredDocuments.length}
      />

      {/* Tabla reactiva de documentos */}
      <DocumentTable documents={filteredDocuments} isLoading={isLoading} />
    </div>
  );
}

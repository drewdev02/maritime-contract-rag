import { Search, X } from "lucide-react";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import { DocumentStatus } from "../types/document.types";

interface DocumentFilterBarProps {
  currentStatus?: DocumentStatus;
  searchQuery: string;
  onStatusChange: (status: DocumentStatus | undefined) => void;
  onSearchChange: (query: string) => void;
  totalCount: number;
}

const STATUS_FILTERS: { label: string; value: DocumentStatus | undefined }[] = [
  { label: "Todos", value: undefined },
  { label: "Pendientes", value: DocumentStatus.PENDING },
  { label: "Procesando", value: DocumentStatus.PROCESSING },
  { label: "Listos", value: DocumentStatus.READY },
  { label: "Fallidos", value: DocumentStatus.FAILED },
];

export const DocumentFilterBar = ({
  currentStatus,
  searchQuery,
  onStatusChange,
  onSearchChange,
  totalCount,
}: DocumentFilterBarProps) => {
  return (
    <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
      {/* Selector de estados estilo Manifiesto Náutico */}
      <div className="flex flex-wrap items-center gap-1.5" data-testid="status-filters">
        {STATUS_FILTERS.map((filter) => {
          const isActive = currentStatus === filter.value;
          return (
            <Button
              key={filter.label}
              type="button"
              variant={isActive ? "default" : "outline"}
              size="sm"
              onClick={() => onStatusChange(filter.value)}
              className={`h-7 text-xs font-medium rounded transition-all ${
                isActive
                  ? "bg-teal-500 hover:bg-teal-400 text-slate-950 font-semibold shadow-xs border border-teal-400"
                  : "bg-[#0B131E] border border-slate-800 text-slate-300 hover:text-white hover:bg-slate-800"
              }`}
            >
              <span>{filter.label}</span>
              {isActive && (
                <Badge
                  variant="secondary"
                  className="ml-1.5 px-1.5 py-0 h-4 text-[10px] font-mono bg-slate-950/30 text-slate-950 rounded font-bold"
                >
                  {totalCount}
                </Badge>
              )}
            </Button>
          );
        })}
      </div>

      {/* Buscador de pólizas por nombre */}
      <div className="relative w-full sm:w-64 shrink-0">
        <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Buscar por nombre..."
          className="w-full h-8 pl-8 pr-8 text-xs bg-[#0B131E] border border-slate-800 rounded focus:outline-none focus:border-teal-500 text-white placeholder:text-slate-500 font-sans"
          data-testid="search-input"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => onSearchChange("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
            title="Limpiar búsqueda"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
};

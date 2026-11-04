import { Link } from "@tanstack/react-router";
import { FileText, MessageSquareText, UploadCloud, Loader2 } from "lucide-react";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/shared/components/ui/table";
import { Button } from "@/shared/components/ui/button";
import { DocumentStatusBadge } from "./DocumentStatusBadge";
import { DocumentStatus, type ContractDocument } from "../types/document.types";

interface DocumentTableProps {
  documents: ContractDocument[];
  isLoading?: boolean;
}

export const DocumentTable = ({ documents, isLoading = false }: DocumentTableProps) => {
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDate = (isoString?: string | null): string => {
    if (!isoString) return "—";
    try {
      const date = new Date(isoString);
      return new Intl.DateTimeFormat("es-ES", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(date);
    } catch {
      return isoString;
    }
  };

  if (isLoading && documents.length === 0) {
    return (
      <div
        data-testid="document-table-loading"
        className="flex flex-col items-center justify-center p-12 text-slate-400 space-y-3 bg-[#0B131E] border border-slate-800 rounded-md"
      >
        <Loader2 className="w-6 h-6 animate-spin text-teal-400" />
        <p className="text-xs font-mono">Cargando contratos marítimos...</p>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div
        data-testid="document-table-empty"
        className="flex flex-col items-center justify-center p-12 text-center bg-[#0B131E] border border-slate-800 rounded-md space-y-4 shadow-xs"
      >
        <div className="p-3 bg-slate-850 rounded-md text-slate-400 border border-slate-800">
          <FileText className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h3 className="font-semibold text-white text-sm">
            No se encontraron contratos registrados
          </h3>
          <p className="text-xs text-slate-400 max-w-sm">
            No hay acuerdos que coincidan con el filtro actual o la base de conocimiento está vacía.
          </p>
        </div>
        <Button asChild size="sm" variant="default" className="gap-2 bg-teal-500 hover:bg-teal-400 text-slate-950 font-semibold rounded text-xs h-8 px-3 shadow-xs">
          <Link to="/upload">
            <UploadCloud className="w-3.5 h-3.5" />
            <span>Subir nuevo contrato</span>
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="border border-slate-800 rounded-md bg-[#0B131E] overflow-hidden shadow-xs">
      <Table data-testid="documents-table">
        <TableHeader>
          <TableRow className="bg-[#090F18] border-b border-slate-800 hover:bg-[#090F18]">
            <TableHead className="w-[38%] font-mono text-[11px] uppercase tracking-wider text-slate-400 font-medium">
              Póliza / Contrato Marítimo
            </TableHead>
            <TableHead className="w-[12%] font-mono text-[11px] uppercase tracking-wider text-slate-400 font-medium">
              Tamaño
            </TableHead>
            <TableHead className="w-[16%] font-mono text-[11px] uppercase tracking-wider text-slate-400 font-medium">
              Fragmentos
            </TableHead>
            <TableHead className="w-[14%] font-mono text-[11px] uppercase tracking-wider text-slate-400 font-medium">
              Fecha
            </TableHead>
            <TableHead className="w-[10%] font-mono text-[11px] uppercase tracking-wider text-slate-400 font-medium">
              Estado
            </TableHead>
            <TableHead className="w-[10%] text-right font-mono text-[11px] uppercase tracking-wider text-slate-400 font-medium">
              Acciones
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((doc) => (
            <TableRow
              key={doc.document_id}
              data-testid={`document-row-${doc.document_id}`}
              className="border-b border-slate-800/80 hover:bg-slate-800/40 transition-colors"
            >
              <TableCell className="font-medium py-3">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-slate-800 text-teal-400 rounded shrink-0 flex items-center justify-center border border-slate-700">
                    <FileText className="w-3.5 h-3.5" />
                  </div>
                  <div className="truncate max-w-xs md:max-w-md">
                    <p className="truncate text-white text-xs font-semibold">
                      {doc.filename}
                    </p>
                    <p className="text-[10px] font-mono text-slate-400 truncate mt-0.5">
                      ID: {doc.document_id.slice(0, 8)}...
                    </p>
                  </div>
                </div>
              </TableCell>

              <TableCell className="text-xs text-slate-300 font-mono py-3">
                {formatFileSize(doc.size_bytes)}
              </TableCell>

              <TableCell className="text-xs text-slate-300 py-3">
                {doc.chunk_count > 0 ? (
                  <span className="font-mono text-[11px] font-medium text-slate-200 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">
                    {doc.chunk_count} {doc.chunk_count === 1 ? "fragmento" : "fragmentos"}
                  </span>
                ) : (
                  <span className="text-slate-400 font-mono text-[11px]">—</span>
                )}
              </TableCell>

              <TableCell className="text-xs text-slate-400 font-mono py-3">
                {formatDate(doc.created_at)}
              </TableCell>

              <TableCell className="py-3">
                <DocumentStatusBadge status={doc.status} errorDetail={doc.error_detail} />
              </TableCell>

              <TableCell className="text-right py-3">
                {doc.status === DocumentStatus.READY ? (
                  <Button
                    asChild
                    size="sm"
                    variant="outline"
                    className="h-7 gap-1.5 text-xs text-slate-200 border-slate-700 bg-slate-800 hover:bg-slate-700 hover:text-white rounded px-2.5"
                  >
                    <Link to="/chat">
                      <MessageSquareText className="w-3 h-3 text-teal-400" />
                      <span>Consultar</span>
                    </Link>
                  </Button>
                ) : (
                  <span className="text-xs text-slate-400 font-mono">—</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};

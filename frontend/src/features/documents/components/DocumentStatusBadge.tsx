import { Loader2, CheckCircle2, Clock, AlertTriangle } from "lucide-react";
import { Badge } from "@/shared/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";
import { DocumentStatus } from "../types/document.types";

interface DocumentStatusBadgeProps {
  status: DocumentStatus;
  errorDetail?: string | null;
}

export const DocumentStatusBadge = ({ status, errorDetail }: DocumentStatusBadgeProps) => {
  switch (status) {
    case DocumentStatus.PENDING:
      return (
        <Badge
          data-testid="status-badge-pending"
          variant="outline"
          className="bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 border-amber-300/80 dark:border-amber-800 gap-1.5 font-medium text-[11px] rounded px-2 py-0.5"
        >
          <Clock className="w-3 h-3 shrink-0" />
          <span>Pendiente</span>
        </Badge>
      );

    case DocumentStatus.PROCESSING:
      return (
        <Badge
          data-testid="status-badge-processing"
          variant="outline"
          className="bg-sky-50 dark:bg-sky-950/40 text-sky-800 dark:text-sky-300 border-sky-300/80 dark:border-sky-800 gap-1.5 font-medium text-[11px] rounded px-2 py-0.5 animate-pulse"
        >
          <Loader2 className="w-3 h-3 shrink-0 animate-spin" />
          <span>Procesando</span>
        </Badge>
      );

    case DocumentStatus.READY:
      return (
        <Badge
          data-testid="status-badge-ready"
          variant="outline"
          className="bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border-teal-300/80 dark:border-teal-800 gap-1.5 font-medium text-[11px] rounded px-2 py-0.5"
        >
          <CheckCircle2 className="w-3 h-3 shrink-0 text-teal-600 dark:text-teal-400" />
          <span>Listo</span>
        </Badge>
      );

    case DocumentStatus.FAILED: {
      const badge = (
        <Badge
          data-testid="status-badge-failed"
          variant="destructive"
          className="bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border border-red-300/80 dark:border-red-800 gap-1.5 font-medium text-[11px] rounded px-2 py-0.5 cursor-help"
        >
          <AlertTriangle className="w-3 h-3 shrink-0 text-red-600 dark:text-red-400" />
          <span>Fallido</span>
        </Badge>
      );

      if (errorDetail) {
        return (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>{badge}</TooltipTrigger>
              <TooltipContent className="max-w-xs text-xs bg-slate-900 text-white border border-slate-700">
                <p className="font-semibold text-red-300 mb-0.5">Motivo del fallo:</p>
                <p>{errorDetail}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        );
      }

      return badge;
    }

    default:
      return (
        <Badge variant="outline" className="gap-1.5 font-medium text-[11px] rounded">
          <span>{status}</span>
        </Badge>
      );
  }
};

import { FileText, ExternalLink, Info } from "lucide-react"
import type { Citation } from "@/types/chat"
import { useCitationStore } from "../../store/useCitationStore"
import { Badge } from "@/shared/components/ui/badge"
import {
  HoverCard,
  HoverCardTrigger,
  HoverCardContent,
} from "@/shared/components/ui/hover-card"

export interface CitationChipProps {
  citation: Citation
}

export function CitationChip({ citation }: CitationChipProps) {
  const openCitation = useCitationStore((state) => state.openCitation)

  return (
    <HoverCard openDelay={200} closeDelay={100}>
      <HoverCardTrigger asChild>
        <button
          type="button"
          onClick={() => openCitation(citation)}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/90 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-medium text-slate-800 dark:text-slate-200 transition-all cursor-pointer group shadow-2xs text-left"
          title="Clic para inspeccionar fragmento en el visor lateral"
        >
          <FileText className="w-3.5 h-3.5 text-[#0C1E32] dark:text-slate-300 shrink-0" />
          <span className="truncate max-w-[170px] font-sans" title={citation.document_name}>
            {citation.document_name}
          </span>
          <Badge
            variant="secondary"
            className="px-1.5 py-0 text-[10px] font-mono bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200 rounded"
          >
            Pág. {citation.page_number}
          </Badge>
          <ExternalLink className="w-3 h-3 text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition-colors ml-0.5 shrink-0 opacity-70 group-hover:opacity-100" />
        </button>
      </HoverCardTrigger>

      <HoverCardContent align="start" className="w-84 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-md shadow-xs">
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-1.5">
            <span className="font-semibold text-xs text-slate-900 dark:text-white truncate">
              {citation.document_name}
            </span>
            <Badge variant="outline" className="text-[10px] font-mono py-0 shrink-0 rounded">
              Página {citation.page_number}
            </Badge>
          </div>

          <div className="text-[11px] text-slate-700 dark:text-slate-300 leading-relaxed italic bg-slate-50 dark:bg-slate-800/60 p-2 rounded border border-slate-200 dark:border-slate-700 max-h-28 overflow-y-auto font-sans">
            "{citation.snippet_text}"
          </div>

          <div className="flex items-center justify-between text-[10px] text-slate-500 pt-0.5">
            <span className="flex items-center gap-1 text-[#0C1E32] dark:text-slate-300 font-medium">
              <Info className="w-3 h-3" />
              Clic para abrir panel completo
            </span>
            <span className="font-mono truncate max-w-[100px] text-slate-400">
              ID: {citation.chunk_id.slice(0, 8)}...
            </span>
          </div>
        </div>
      </HoverCardContent>
    </HoverCard>
  )
}

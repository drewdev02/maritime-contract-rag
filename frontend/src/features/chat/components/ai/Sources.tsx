"use client"

import { Globe, FileText, ExternalLink } from "lucide-react"
import type { Citation } from "@/types/chat"
import { useCitationStore } from "../../store/useCitationStore"
import {
  Trace,
  TraceCollapsible,
  TraceCollapsibleTrigger,
  TraceCollapsibleContent,
  TraceIcon,
  TraceTitle,
} from "@/shared/components/ui/trace"

export interface SourcesProps {
  citations: Citation[]
}

export function Sources({ citations }: SourcesProps) {
  const openCitation = useCitationStore((state) => state.openCitation)

  if (!citations || citations.length === 0) {
    return null
  }

  // Deduplicate by document_name
  const uniqueDocs = Array.from(
    new Map(citations.map((c) => [c.document_id, c])).values()
  )

  return (
    <Trace className="my-2">
      <TraceCollapsible>
        <TraceCollapsibleTrigger>
          <TraceIcon>
            <Globe className="text-indigo-500" />
          </TraceIcon>
          <TraceTitle>
            Fuentes consultadas ({uniqueDocs.length} {uniqueDocs.length === 1 ? "contrato" : "contratos"})
          </TraceTitle>
        </TraceCollapsibleTrigger>
        <TraceCollapsibleContent>
          <div className="flex flex-col gap-1.5 pt-1">
            {citations.map((c) => (
              <button
                key={`${c.chunk_id}-${c.page_number}`}
                type="button"
                onClick={() => openCitation(c)}
                className="flex items-center justify-between text-left hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors group cursor-pointer"
              >
                <div className="flex items-center gap-1.5 truncate">
                  <FileText className="w-3.5 h-3.5 text-slate-400 group-hover:text-indigo-500 shrink-0" />
                  <span className="truncate max-w-[220px] font-sans font-medium text-xs">
                    {c.document_name}
                  </span>
                  <span className="text-[10px] text-slate-400">
                    (Pág. {c.page_number})
                  </span>
                </div>
                <ExternalLink className="w-3 h-3 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-2" />
              </button>
            ))}
          </div>
        </TraceCollapsibleContent>
      </TraceCollapsible>
    </Trace>
  )
}

"use client"

import { HoverCard, HoverCardTrigger, HoverCardContent } from "@/shared/components/ui/hover-card"
import { Button } from "@/shared/components/ui/button"
import { FileText, Info } from "lucide-react"
import type { Citation } from "@/types/chat"
import { useCitationStore } from "../../store/useCitationStore"

export interface InlineCitationProps {
  citation: Citation
}

export function InlineCitation({ citation }: InlineCitationProps) {
  const openCitation = useCitationStore((state) => state.openCitation)

  return (
    <HoverCard openDelay={10} closeDelay={100}>
      <HoverCardTrigger asChild>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => openCitation(citation)}
          className="h-6 px-2 py-0 text-xs font-medium rounded-md gap-1 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200/80 dark:border-indigo-800/80 hover:bg-indigo-100 dark:hover:bg-indigo-900 cursor-pointer inline-flex items-center"
        >
          <FileText className="w-3 h-3 text-indigo-500" />
          <span className="truncate max-w-[140px]">{citation.document_name}</span>
          <span className="font-semibold text-[10px] text-indigo-900 dark:text-indigo-200">
            Pág. {citation.page_number}
          </span>
        </Button>
      </HoverCardTrigger>
      <HoverCardContent className="w-80 flex flex-col gap-2 p-3.5 shadow-lg border-slate-200 dark:border-slate-800">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-1.5">
          <span className="font-semibold text-xs text-slate-900 dark:text-white truncate">
            {citation.document_name}
          </span>
          <span className="text-[10px] bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded font-mono">
            Pág. {citation.page_number}
          </span>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-300 italic font-mono bg-slate-50 dark:bg-slate-900 p-2 rounded border border-slate-100 dark:border-slate-800/80 leading-relaxed">
          "{citation.snippet_text}"
        </p>
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span className="flex items-center gap-1 text-indigo-600 dark:text-indigo-400 font-medium">
            <Info className="w-3 h-3" />
            Clic para abrir en panel lateral
          </span>
          <span className="font-mono text-slate-400">
            {citation.chunk_id.slice(0, 8)}...
          </span>
        </div>
      </HoverCardContent>
    </HoverCard>
  )
}

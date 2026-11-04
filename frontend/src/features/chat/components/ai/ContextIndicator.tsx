"use client"

import { Database, CheckCircle2 } from "lucide-react"
import { HoverCard, HoverCardTrigger, HoverCardContent } from "@/shared/components/ui/hover-card"
import { Button } from "@/shared/components/ui/button"
import { Badge } from "@/shared/components/ui/badge"

export interface ContextIndicatorProps {
  documentCount?: number
  chunkCount?: number
}

export function ContextIndicator({
  documentCount = 1,
  chunkCount = 3,
}: ContextIndicatorProps) {
  return (
    <HoverCard openDelay={100} closeDelay={100}>
      <HoverCardTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1.5 text-xs text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-800"
        >
          <Database className="w-3.5 h-3.5 text-indigo-500" />
          <span>Base de Conocimiento</span>
          <Badge variant="secondary" className="text-[10px] py-0 px-1 font-mono">
            {documentCount} {documentCount === 1 ? "contrato" : "contratos"}
          </Badge>
        </Button>
      </HoverCardTrigger>
      <HoverCardContent className="w-72 p-3 text-xs flex flex-col gap-2">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-1.5 font-semibold">
          <span>Contexto Indexado RAG</span>
          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-medium">
            <CheckCircle2 className="w-3 h-3" /> pgvector activo
          </span>
        </div>
        <div className="space-y-1 text-slate-500">
          <div className="flex justify-between">
            <span>Contratos en estado READY:</span>
            <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold">{documentCount}</span>
          </div>
          <div className="flex justify-between">
            <span>Fragmentos Vectoriales (768-dim):</span>
            <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold">{chunkCount}</span>
          </div>
          <div className="flex justify-between">
            <span>Métrica de similitud:</span>
            <span className="font-mono text-slate-800 dark:text-slate-200">Distancia Coseno (&lt;=&gt;)</span>
          </div>
        </div>
      </HoverCardContent>
    </HoverCard>
  )
}

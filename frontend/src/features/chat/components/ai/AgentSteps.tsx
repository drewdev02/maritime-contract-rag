import * as React from "react"
import { ChevronDown, Database, ShieldCheck, CheckCircle2, AlertTriangle, Layers } from "lucide-react"
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/shared/components/ui/collapsible"
import { cn } from "@/shared/utils/cn"

export interface AgentStepsProps {
  confidenceScore?: number | null
  hasSufficientEvidence?: boolean
  citationsCount?: number
  className?: string
}

export function AgentSteps({
  confidenceScore,
  hasSufficientEvidence = true,
  citationsCount = 0,
  className,
}: AgentStepsProps) {
  const [isOpen, setIsOpen] = React.useState(false)

  const similarityPercent = confidenceScore != null ? Math.round(confidenceScore * 100) : null

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className={cn(
        "w-full rounded-xl border border-slate-200/80 dark:border-slate-800/80 bg-slate-50/70 dark:bg-slate-900/40 text-xs overflow-hidden",
        className
      )}
    >
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-slate-100/60 dark:hover:bg-slate-800/60 transition-colors cursor-pointer text-slate-600 dark:text-slate-300 select-none font-medium"
        >
          <div className="flex items-center gap-2">
            <Layers className="w-3.5 h-3.5 text-indigo-500" />
            <span>Trazabilidad de Ejecución RAG</span>
            <span className="text-[10px] text-slate-400 font-mono">
              (3 etapas)
            </span>
          </div>
          <ChevronDown
            className={cn(
              "w-3.5 h-3.5 text-slate-400 transition-transform duration-200",
              isOpen && "rotate-180"
            )}
          />
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent className="px-3 pb-3 pt-1 border-t border-slate-200/50 dark:border-slate-800/50 space-y-2 font-mono text-[11px]">
        {/* Step 1: Vector Search */}
        <div className="flex items-start gap-2 text-slate-600 dark:text-slate-300">
          <Database className="w-3.5 h-3.5 text-indigo-500 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold text-slate-800 dark:text-slate-200">1. Recuperación:</span>{" "}
            pgvector (Cosine Distance) en fragmentos con estado READY.
            {similarityPercent != null && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300">
                Similitud: {similarityPercent}%
              </span>
            )}
          </div>
        </div>

        {/* Step 2: Sufficiency */}
        <div className="flex items-start gap-2 text-slate-600 dark:text-slate-300">
          {hasSufficientEvidence ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
          ) : (
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
          )}
          <div className="flex-1">
            <span className="font-semibold text-slate-800 dark:text-slate-200">2. Suficiencia Documental:</span>{" "}
            {hasSufficientEvidence
              ? "Evidencia probatoria suficiente verificada en base de conocimiento."
              : "Abstención declarada: no se superó el umbral de suficiencia semántica."}
          </div>
        </div>

        {/* Step 3: Anti-hallucination validation */}
        <div className="flex items-start gap-2 text-slate-600 dark:text-slate-300">
          <ShieldCheck className="w-3.5 h-3.5 text-indigo-500 shrink-0 mt-0.5" />
          <div className="flex-1">
            <span className="font-semibold text-slate-800 dark:text-slate-200">3. Validación Anti-Alucinación:</span>{" "}
            {citationsCount > 0
              ? `${citationsCount} cita(s) textual(es) verificada(s) verbatim contra la base de datos.`
              : "Sin citas requeridas (respuesta de cortesía o abstención)."}
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

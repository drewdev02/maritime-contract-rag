"use client"

import { Brain, Database, ShieldCheck, CheckCircle2, AlertTriangle } from "lucide-react"
import {
  Trace,
  TraceCollapsible,
  TraceCollapsibleTrigger,
  TraceCollapsibleContent,
  TraceIcon,
  TraceTitle,
  TraceDescription,
} from "@/shared/components/ui/trace"

export interface ReasoningProps {
  confidenceScore?: number | null
  hasSufficientEvidence?: boolean
  citationsCount?: number
}

export function Reasoning({
  confidenceScore,
  hasSufficientEvidence = true,
  citationsCount = 0,
}: ReasoningProps) {
  const similarityPercent = confidenceScore != null ? Math.round(confidenceScore * 100) : null

  return (
    <Trace className="my-2">
      <TraceCollapsible>
        <TraceCollapsibleTrigger>
          <TraceIcon>
            <Brain className="text-indigo-500" />
          </TraceIcon>
          <TraceTitle>Razonamiento y trazabilidad RAG</TraceTitle>
          {similarityPercent != null && (
            <TraceDescription>
              ({similarityPercent}% similitud)
            </TraceDescription>
          )}
        </TraceCollapsibleTrigger>
        <TraceCollapsibleContent>
          <div className="flex flex-col gap-2 pt-1 font-mono text-[11px]">
            {/* Step 1: Vector Search */}
            <div className="flex items-start gap-2">
              <Database className="w-3.5 h-3.5 text-indigo-500 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  1. Recuperación Vectorial:
                </span>{" "}
                Búsqueda semántica
                {similarityPercent != null && (
                  <span className="ml-1.5 px-1.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 font-semibold">
                    Similitud: {similarityPercent}%
                  </span>
                )}
              </div>
            </div>

            {/* Step 2: Sufficiency */}
            <div className="flex items-start gap-2">
              {hasSufficientEvidence ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
              )}
              <div>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  2. Suficiencia Documental:
                </span>{" "}
                {hasSufficientEvidence
                  ? "Evidencia probatoria suficiente verificada en base de conocimiento."
                  : "Abstención declarada: no se superó el umbral de suficiencia semántica."}
              </div>
            </div>

            {/* Step 3: Anti-hallucination validation */}
            <div className="flex items-start gap-2">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-500 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  3. Verificación Anti-Alucinación:
                </span>{" "}
                {citationsCount > 0
                  ? `${citationsCount} cita(s) textual(es) validada(s) verbatim contra la base de datos.`
                  : "Sin citas requeridas."}
              </div>
            </div>
          </div>
        </TraceCollapsibleContent>
      </TraceCollapsible>
    </Trace>
  )
}

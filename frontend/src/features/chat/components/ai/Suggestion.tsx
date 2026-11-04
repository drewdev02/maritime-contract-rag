"use client"

import { Button } from "@/shared/components/ui/button"
import { cn } from "@/shared/utils/cn"

export interface SuggestionProps {
  label: string
  query: string
  onClick: (query: string) => void
  className?: string
}

export function Suggestion({ label, query, onClick, className }: SuggestionProps) {
  return (
    <Button
      variant="outline"
      size="sm"
      type="button"
      onClick={() => onClick(query)}
      className={cn(
        "cursor-pointer rounded px-3 py-1.5 h-auto text-xs font-normal border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/80 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-all shadow-2xs text-left",
        className
      )}
    >
      <span className="font-semibold text-[#0C1E32] dark:text-teal-400 mr-1.5 font-sans">
        {label}
      </span>
      <span className="text-slate-600 dark:text-slate-400">{query}</span>
    </Button>
  )
}

export const MARITIME_SUGGESTIONS = [
  {
    label: "Tarifa TEU estándar",
    query: "¿Cuál es la tarifa acordada por contenedor TEU?",
  },
  {
    label: "Días libres de demoras",
    query: "¿Cuántos días libres de demoras se contemplan en terminal?",
  },
  {
    label: "Tráfico transatlántico",
    query: "¿Qué condiciones tarifarias aplican para tráfico transatlántico?",
  },
  {
    label: "Contenedores Reefer",
    query: "¿Qué sobrecargo aplica por conexión eléctrica o cold treatment en contenedores refrigerados?",
  },
]

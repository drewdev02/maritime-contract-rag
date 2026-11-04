"use client"

import { useState, type KeyboardEvent, type FormEvent } from "react"
import { Loader2, CornerDownLeft, Compass, Square } from "lucide-react"
import {
  InputGroup,
  InputGroupTextarea,
  InputGroupAddon,
  InputGroupButton,
} from "@/shared/components/ui/input-group"

export interface PromptInputProps {
  onSubmit: (query: string) => void
  isLoading: boolean
  isStreaming?: boolean
  onStop?: () => void
}

export function PromptInput({ onSubmit, isLoading, isStreaming, onStop }: PromptInputProps) {
  const [query, setQuery] = useState("")

  const handleSubmit = (e?: FormEvent) => {
    if (e) e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed || isLoading || isStreaming) return
    onSubmit(trimmed)
    setQuery("")
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full relative flex flex-col gap-2">
      <InputGroup className="border border-slate-800 rounded-md bg-[#0B131E] shadow-2xs focus-within:border-teal-500/60 has-[[data-slot=input-group-control]:focus-visible]:ring-1 has-[[data-slot=input-group-control]:focus-visible]:ring-teal-500/30 transition-colors">
        {/* Nivel Superior: Área de Redacción de la Consulta */}
        <div className="flex items-start w-full px-3.5 pt-3 pb-1">
          <Compass className="w-4 h-4 text-slate-400 dark:text-slate-500 shrink-0 mt-1 mr-2.5" />
          <InputGroupTextarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onInput={(e) => setQuery((e.target as HTMLTextAreaElement).value)}
            onKeyDown={handleKeyDown}
            placeholder="Formula una pregunta sobre tarifas, demoras o cláusulas marítimas..."
            disabled={isLoading}
            rows={2}
            className="w-full min-h-[56px] resize-none bg-transparent text-xs sm:text-sm text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none disabled:opacity-50 font-sans leading-relaxed"
          />
        </div>

        {/* Nivel Inferior: Barra de Despacho y Atajos a Ancho Completo */}
        <InputGroupAddon align="block-end">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400 select-none font-mono">
            <span>Presiona</span>
            <kbd className="px-1.5 py-0.5 rounded bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono text-[10px] border border-slate-200 dark:border-slate-700 font-semibold shadow-2xs">
              Enter
            </kbd>
            <span>para enviar,</span>
            <kbd className="px-1.5 py-0.5 rounded bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono text-[10px] border border-slate-200 dark:border-slate-700 font-semibold shadow-2xs">
              Shift + Enter
            </kbd>
            <span>para salto de línea</span>
          </div>

          {isStreaming && onStop ? (
            <InputGroupButton
              type="button"
              onClick={onStop}
              className="bg-red-600 hover:bg-red-700 text-white font-semibold text-xs rounded shadow-xs cursor-pointer h-8 px-3.5 transition-colors"
            >
              <Square className="w-3.5 h-3.5 mr-1.5 fill-current" />
              <span>Detener</span>
            </InputGroupButton>
          ) : (
            <InputGroupButton
              type="submit"
              disabled={isLoading || isStreaming || !query.trim()}
              className="bg-[#0C1E32] hover:bg-[#152e4d] text-white dark:bg-teal-500 dark:hover:bg-teal-400 dark:text-slate-950 font-semibold text-xs rounded shadow-xs cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed h-8 px-3.5 transition-colors"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                  <span>Analizando...</span>
                </>
              ) : (
                <>
                  <span>Consultar</span>
                  <CornerDownLeft className="w-3.5 h-3.5 ml-1.5" />
                </>
              )}
            </InputGroupButton>
          )}
        </InputGroupAddon>
      </InputGroup>
    </form>
  )
}

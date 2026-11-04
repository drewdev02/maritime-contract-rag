import { Sparkles } from "lucide-react"
import { Suggestion, MARITIME_SUGGESTIONS } from "./Suggestion"

export interface PromptSuggestionsProps {
  onSelectPrompt: (prompt: string) => void
}

export { MARITIME_SUGGESTIONS as MARITIME_PROMPT_SUGGESTIONS }

export function PromptSuggestions({ onSelectPrompt }: PromptSuggestionsProps) {
  return (
    <div className="w-full max-w-xl flex flex-col gap-2.5">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 text-left flex items-center gap-1.5">
        <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
        Consultas de muestra sugeridas:
      </p>
      <div className="flex flex-wrap gap-2 justify-center sm:justify-start">
        {MARITIME_SUGGESTIONS.map((item) => (
          <Suggestion
            key={item.label}
            label={item.label}
            query={item.query}
            onClick={onSelectPrompt}
          />
        ))}
      </div>
    </div>
  )
}

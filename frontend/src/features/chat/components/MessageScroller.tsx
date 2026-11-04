import { useRef, useEffect } from "react";
import { Bot, Loader2, Anchor } from "lucide-react";
import type { ChatMessage } from "@/types/chat";
import { Message } from "./ai/Message";
import { PromptSuggestions } from "./ai/PromptSuggestions";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/shared/components/ui/avatar";

export interface MessageScrollerProps {
  messages: ChatMessage[];
  onSelectPrompt: (prompt: string) => void;
  isLoading: boolean;
}

export function MessageScroller({ messages, onSelectPrompt, isLoading }: MessageScrollerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-slate-900/60 rounded-md border border-slate-200 dark:border-slate-800 shadow-2xs">
        <div className="w-10 h-10 rounded-md bg-[#0C1E32] flex items-center justify-center text-white mb-3 shadow-xs">
          <Anchor className="w-5 h-5" />
        </div>
        <h3 className="text-sm font-bold text-slate-900 dark:text-white">
          Asistente RAG de Contratos Marítimos
        </h3>
        <p className="text-xs text-slate-500 max-w-md mt-1 mb-6 leading-relaxed">
          Formula consultas en lenguaje natural para contrastar tarifas, días de demora y cláusulas operativas con verificación estricta de citas textuales.
        </p>

        <PromptSuggestions onSelectPrompt={onSelectPrompt} />
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1 pr-3">
      <div className="space-y-4 pb-4">
        {messages
          // El indicador "Consultando..." cubre la espera: no se muestra una burbuja vacía.
          .filter((msg) => !(msg.sender === "assistant" && msg.isStreaming && msg.text.length === 0))
          .map((msg) => (
            <Message key={msg.id} message={msg} />
          ))}

        {isLoading && !messages.some((m) => m.isStreaming && m.text.length > 0) && (
          <div className="flex gap-3 justify-start">
            <Avatar className="mt-0.5 rounded-md bg-[#0C1E32] text-white shrink-0 h-8 w-8">
              <AvatarFallback className="bg-[#0C1E32] text-white">
                <Bot className="w-4 h-4" />
              </AvatarFallback>
            </Avatar>
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-md p-3.5 text-xs text-slate-600 dark:text-slate-300 flex items-center gap-3 shadow-2xs">
              <Loader2 className="w-4 h-4 animate-spin text-[#0C1E32] dark:text-teal-400 shrink-0" />
              <div className="space-y-0.5">
                <p className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                  Consultando base de conocimiento vectorial...
                </p>
                <p className="text-[11px] font-mono text-slate-400">
                  Calculando distancia coseno en pgvector y verificando suficiencia probatoria.
                </p>
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}

import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RotateCcw, Anchor } from "lucide-react";
import { toast } from "sonner";

import type { ChatMessage } from "@/types/chat";
import { DocumentStatus } from "@/features/documents/types/document.types";
import { useDocuments } from "@/features/documents/api/useDocuments";
import { useStreamingChat } from "@/features/chat/api/useChat";
import { MessageScroller } from "@/features/chat/components/MessageScroller";
import { PromptInput } from "@/features/chat/components/PromptInput";
import { CitationSheet } from "@/features/chat/components/CitationSheet";
import { ContextIndicator } from "@/features/chat/components/ai/ContextIndicator";
import { Button } from "@/shared/components/ui/button";

export const Route = createFileRoute("/chat")({
  component: ChatPage,
});

function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const { streamQuery, stop, isStreaming } = useStreamingChat();
  const { data: readyDocs = [] } = useDocuments({ status: DocumentStatus.READY });

  const readyCount = readyDocs.length;
  const chunksCount = readyDocs.reduce((acc, doc) => acc + (doc.chunk_count ?? 0), 0);

  const handleSendQuery = (queryText: string) => {
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: queryText,
      timestamp: new Date(),
    };

    const assistantId = `assistant-${Date.now()}`;
    const assistantMessage: ChatMessage = {
      id: assistantId,
      sender: "assistant",
      text: "",
      isStreaming: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);

    streamQuery(
      { query: queryText, top_k: 5 },
      {
        onToken: (delta) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId ? { ...msg, text: msg.text + delta } : msg
            )
          );
        },
        onMeta: (data) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? {
                    ...msg,
                    citations: data.citations,
                    has_sufficient_evidence: data.has_sufficient_evidence,
                    confidence_score: data.confidence_score,
                  }
                : msg
            )
          );

          if (!data.has_sufficient_evidence) {
            toast.warning("Respuesta con evidencia insuficiente en contratos.");
          } else if (data.citations.length > 0) {
            toast.success(`${data.citations.length} citas textuales verificadas.`);
          }
        },
        onDone: () => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId ? { ...msg, isStreaming: false } : msg
            )
          );
        },
        onError: (error) => {
          toast.error("Error al procesar la consulta con el asistente RAG.");
          const errorMessageText = `Se produjo un error al consultar el asistente: ${error.message}`;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId
                ? {
                    ...msg,
                    text: msg.text
                      ? `${msg.text}\n\n[Error: ${error.message}]`
                      : errorMessageText,
                    has_sufficient_evidence: false,
                    isStreaming: false,
                  }
                : msg
            )
          );
        },
      }
    );
  };

  const handleClearChat = () => {
    stop();
    setMessages([]);
    toast.info("Historial de conversación reiniciado.");
  };

  return (
    <div className="flex flex-col flex-1 min-h-0 h-[calc(100vh-3.5rem)]">
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-6 py-3">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-[#0C1E32] text-white rounded shrink-0">
              <Anchor className="w-4 h-4" />
            </div>
            <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
              Asistente RAG de Contratos
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Búsqueda semántica en contratos listos con citas textuales exactas y trazabilidad probatoria.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <ContextIndicator documentCount={readyCount} chunkCount={chunksCount} />

          {messages.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearChat}
              disabled={isStreaming}
              className="h-8 text-xs gap-1.5 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-800 rounded cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reiniciar</span>
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        <div className="flex-1 min-h-0 flex flex-col px-6 pt-4 max-w-6xl w-full mx-auto">
          <MessageScroller
            messages={messages}
            onSelectPrompt={handleSendQuery}
            isLoading={isStreaming}
          />
        </div>

        <div className="shrink-0 w-full border-t border-slate-800 bg-[#0B131E]/90 px-6 py-3">
          <PromptInput
            onSubmit={handleSendQuery}
            isLoading={isStreaming}
            isStreaming={isStreaming}
            onStop={stop}
          />
        </div>
      </div>

      {/* Visor Lateral de Cita Certificada */}
      <CitationSheet />
    </div>
  );
}

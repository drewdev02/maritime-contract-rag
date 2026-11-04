"use client"

import * as React from "react"
import { Bot, User, Copy, Check } from "lucide-react"
import type { ChatMessage } from "@/types/chat"
import {
  Message as UiMessage,
  MessageAvatar,
  MessageContent,
  MessageHeader,
} from "@/shared/components/ui/message"
import { Bubble, BubbleContent } from "@/shared/components/ui/bubble"
import { Avatar, AvatarFallback } from "@/shared/components/ui/avatar"
import { Badge } from "@/shared/components/ui/badge"
import { Reasoning } from "./Reasoning"
import { Sources } from "./Sources"
import { InlineCitation } from "./InlineCitation"
import { SufficientEvidenceAlert } from "../SufficientEvidenceAlert"
import { cn } from "@/shared/utils/cn"

export interface MessageProps {
  message: ChatMessage
  className?: string
}

export function Message({ message, className }: MessageProps) {
  const [copied, setCopied] = React.useState(false)
  const isAssistant = message.sender === "assistant"

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Ignored
    }
  }

  return (
    <UiMessage
      align={isAssistant ? "start" : "end"}
      className={cn("group", className)}
    >
      {isAssistant && (
        <MessageAvatar>
          <Avatar className="h-8 w-8 rounded-md bg-[#0C1E32] text-white shadow-2xs">
            <AvatarFallback className="bg-[#0C1E32] text-white">
              <Bot className="w-4 h-4" />
            </AvatarFallback>
          </Avatar>
        </MessageAvatar>
      )}

      <MessageContent>
        {isAssistant && (
          <MessageHeader>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-xs text-slate-900 dark:text-white">
                Asistente Naviera Portecho
              </span>
              <span className="text-[10px] font-mono uppercase bg-slate-100 dark:bg-slate-800 text-slate-500 px-1 py-0.2 rounded border border-slate-200 dark:border-slate-700">
                {(message.citations && message.citations.length > 0) || (message.confidence_score && message.confidence_score > 0)
                  ? "Dictamen RAG"
                  : "Asistente"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {message.confidence_score !== undefined && message.confidence_score !== null && message.confidence_score > 0 && (
                <Badge variant="outline" className="text-[10px] py-0 text-slate-600 dark:text-slate-300 font-mono rounded">
                  Similitud: {Math.round(message.confidence_score * 100)}%
                </Badge>
              )}
              <button
                type="button"
                onClick={handleCopy}
                title="Copiar texto de respuesta"
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-teal-600" />
                ) : (
                  <Copy className="w-3.5 h-3.5" />
                )}
              </button>
            </div>
          </MessageHeader>
        )}

        <Bubble
          variant={isAssistant ? "muted" : "default"}
          align={isAssistant ? "start" : "end"}
          className={
            isAssistant
              ? "bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100 rounded-md p-4 shadow-2xs"
              : "bg-[#0C1E32] text-white border border-[#0C1E32] rounded-md p-3.5 shadow-2xs"
          }
        >
          {/* Reasoning / Thinking Step from AI Elements */}
          {isAssistant && message.confidence_score !== undefined && message.confidence_score !== null && message.confidence_score > 0 && (
            <Reasoning
              confidenceScore={message.confidence_score}
              hasSufficientEvidence={message.has_sufficient_evidence ?? true}
              citationsCount={message.citations?.length ?? 0}
            />
          )}

          {/* Message Text Body */}
          <BubbleContent>
            <div className="whitespace-pre-wrap leading-relaxed select-text font-sans text-xs sm:text-sm">
              {message.text}
              {message.isStreaming && (
                <span className="inline-block w-1.5 h-3.5 bg-teal-500 ml-1 animate-pulse align-middle" />
              )}
            </div>
          </BubbleContent>

          {/* Insufficient Evidence Alert */}
          {isAssistant && message.has_sufficient_evidence === false && (
            <div className="mt-3">
              <SufficientEvidenceAlert />
            </div>
          )}

          {/* Sources and Inline Citations from AI Elements */}
          {isAssistant && message.citations && message.citations.length > 0 && (
            <div className="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800">
              <Sources citations={message.citations} />

              <div className="mt-2.5 flex flex-wrap gap-1.5 items-center">
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mr-1 font-medium">
                  Citas Verificadas:
                </span>
                {message.citations.map((citation) => (
                  <InlineCitation
                    key={`${citation.chunk_id}-${citation.page_number}`}
                    citation={citation}
                  />
                ))}
              </div>
            </div>
          )}
        </Bubble>
      </MessageContent>

      {!isAssistant && (
        <MessageAvatar>
          <Avatar className="h-8 w-8 rounded-md bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 shadow-2xs">
            <AvatarFallback className="bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
              <User className="w-4 h-4" />
            </AvatarFallback>
          </Avatar>
        </MessageAvatar>
      )}
    </UiMessage>
  )
}

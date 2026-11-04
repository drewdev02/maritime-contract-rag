import { Hash, Bookmark, ShieldCheck, Anchor, ExternalLink } from "lucide-react";
import { useCitationStore } from "../store/useCitationStore";
import { documentPdfUrl, useChunk } from "../api/useChunk";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/shared/components/ui/sheet";
import { Badge } from "@/shared/components/ui/badge";

/** Splits the fragment around the cited snippet (case-insensitive) so it can be highlighted. */
export const splitAroundSnippet = (
  text: string,
  snippet: string,
): { before: string; match: string; after: string } | null => {
  const index = text.toLowerCase().indexOf(snippet.trim().toLowerCase());
  if (index < 0 || !snippet.trim()) return null;
  const end = index + snippet.trim().length;
  return { before: text.slice(0, index), match: text.slice(index, end), after: text.slice(end) };
};

export function CitationSheet() {
  const { activeCitation, isOpen, setOpen } = useCitationStore();
  const chunkQuery = useChunk(activeCitation?.document_id, activeCitation?.chunk_id);

  if (!activeCitation) {
    return null;
  }

  const chunk = chunkQuery.data;
  const parts = chunk ? splitAroundSnippet(chunk.text, activeCitation.snippet_text) : null;

  return (
    <Sheet open={isOpen} onOpenChange={setOpen}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-lg flex flex-col p-6 overflow-y-auto bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800"
      >
        <SheetHeader className="text-left border-b border-slate-200 dark:border-slate-800 pb-4">
          <div className="flex items-center gap-2 mb-1.5">
            <div className="p-1.5 bg-[#0C1E32] text-white rounded shrink-0">
              <Anchor className="w-4 h-4" />
            </div>
            <Badge
              variant="outline"
              className="text-xs bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border-slate-300 dark:border-slate-700 font-mono rounded"
            >
              Página {activeCitation.page_number}
            </Badge>
            <Badge
              variant="outline"
              className="text-xs bg-teal-50 dark:bg-teal-950/40 text-teal-800 dark:text-teal-300 border-teal-300/80 dark:border-teal-800 font-mono rounded flex items-center gap-1"
            >
              <ShieldCheck className="w-3 h-3" />
              VERIFICADO
            </Badge>
          </div>

          <SheetTitle className="text-sm font-bold text-slate-900 dark:text-white break-words">
            {activeCitation.document_name}
          </SheetTitle>

          <SheetDescription className="text-xs text-slate-500 flex flex-col gap-1 mt-1 font-mono">
            <span className="flex items-center gap-1 text-[11px] text-slate-500">
              <Bookmark className="w-3 h-3 text-slate-400 shrink-0" />
              PÓLIZA ID: {activeCitation.document_id}
            </span>
            <span className="flex items-center gap-1 text-[11px] text-slate-500">
              <Hash className="w-3 h-3 text-slate-400 shrink-0" />
              FRAGMENTO VECTORIAL: {activeCitation.chunk_id}
            </span>
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 py-4 flex flex-col gap-4">
          <div>
            <h4 className="text-[11px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2 font-medium">
              Extracto Textual Verificado en Contrato
            </h4>
            <div className="p-4 rounded-md border-l-2 border-l-teal-600 border border-slate-200 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-800/40 text-slate-900 dark:text-slate-100 text-xs leading-relaxed font-sans shadow-2xs whitespace-pre-wrap select-text">
              {activeCitation.snippet_text}
            </div>
          </div>

          <div>
            <h4 className="text-[11px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2 font-medium">
              Fragmento original
              {chunk ? ` · página ${chunk.page_number} · posición ${chunk.start_char}-${chunk.end_char}` : ""}
            </h4>
            {chunkQuery.isLoading && (
              <p data-testid="chunk-loading" className="text-xs text-slate-500">
                Cargando fragmento…
              </p>
            )}
            {chunkQuery.isError && (
              <p data-testid="chunk-error" className="text-xs text-amber-700 dark:text-amber-400">
                No se pudo cargar el fragmento original. Se muestra el extracto citado.
              </p>
            )}
            {chunk && (
              <div
                data-testid="chunk-text"
                className="p-4 rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 text-xs leading-relaxed whitespace-pre-wrap select-text"
              >
                {parts ? (
                  <>
                    {parts.before}
                    <mark className="bg-teal-200/70 dark:bg-teal-700/50 text-inherit rounded-sm px-0.5">
                      {parts.match}
                    </mark>
                    {parts.after}
                  </>
                ) : (
                  chunk.text
                )}
              </div>
            )}
          </div>

          <a
            href={documentPdfUrl(activeCitation.document_id, activeCitation.page_number)}
            target="_blank"
            rel="noopener noreferrer"
            data-testid="open-pdf-link"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-[#0C1E32] dark:text-slate-200 underline underline-offset-2 hover:opacity-80"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Abrir el PDF original en la página {activeCitation.page_number}
          </a>

          <div className="p-3.5 rounded-md bg-slate-100/70 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-400">
            <p className="font-semibold text-slate-800 dark:text-slate-200 mb-1 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
              Cotejo Cruzado Anti-Alucinación
            </p>
            <p className="text-[11px] leading-relaxed">
              Este extracto corresponde exactamente a los fragmentos vectoriales recuperados desde PostgreSQL pgvector y validados mediante comparación textual cruzada verbatim en el backend.
            </p>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

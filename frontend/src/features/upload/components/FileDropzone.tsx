import { useState, useRef, type DragEvent, type ChangeEvent } from "react";
import { UploadCloud, FileText, X, Loader2, AlertCircle, FileCheck, Anchor } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Alert, AlertDescription } from "@/shared/components/ui/alert";
import { uploadFileSchema } from "../types";
import { useUploadDocument } from "../api/useUploadDocument";
import type { BatchUploadResponse } from "../types";

interface FileDropzoneProps {
  onSuccess?: (result: BatchUploadResponse) => void;
}

export const FileDropzone = ({ onSuccess }: FileDropzoneProps) => {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadMutation = useUploadDocument();

  const validateAndAddFiles = (incoming: File[]) => {
    const valid: File[] = [];
    let firstError: string | null = null;
    for (const file of incoming) {
      const result = uploadFileSchema.safeParse({ file });
      if (result.success) {
        valid.push(file);
      } else {
        firstError ??= `${file.name}: ${result.error.issues[0]?.message || "Archivo inválido."}`;
      }
    }

    setValidationError(firstError);
    if (firstError) toast.error(firstError);
    if (valid.length > 0) {
      setSelectedFiles((current) => {
        const known = new Set(current.map((f) => `${f.name}:${f.size}`));
        return [...current, ...valid.filter((f) => !known.has(`${f.name}:${f.size}`))];
      });
    }
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);

    const dropped = Array.from(e.dataTransfer.files);
    if (dropped.length > 0) {
      validateAndAddFiles(dropped);
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? []);
    if (picked.length > 0) {
      validateAndAddFiles(picked);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRemoveFile = (target: File) => {
    setSelectedFiles((current) => current.filter((f) => f !== target));
    setValidationError(null);
  };

  const handleUpload = () => {
    if (selectedFiles.length === 0) return;

    uploadMutation.mutate(selectedFiles, {
      onSuccess: (data) => {
        if (data.accepted > 0) {
          toast.success(`${data.accepted} contrato(s) subido(s) con éxito`, {
            description: "El procesamiento continúa en segundo plano.",
          });
        }
        for (const item of data.items) {
          if (item.error) {
            toast.error(`No se pudo subir "${item.filename}"`, { description: item.error });
          }
        }
        // Keep only rejected files so the user can see what still needs attention.
        const rejected = new Set(data.items.filter((i) => i.error).map((i) => i.filename));
        setSelectedFiles((current) => current.filter((f) => rejected.has(f.name)));
        if (data.accepted > 0 && onSuccess) {
          onSuccess(data);
        }
      },
      onError: (err: unknown) => {
        const errorMsg =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          "Error al subir los contratos al servidor.";
        toast.error("Error en la subida", { description: errorMsg });
      },
    });
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-4">
      {/* Bahía de Atraque Documental / Dropzone Container */}
      <div
        data-testid="dropzone"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !uploadMutation.isPending && fileInputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center p-10 min-h-[360px] border border-dashed rounded-lg cursor-pointer transition-all duration-150 ${
          isDragging
            ? "border-[#0C1E32] bg-slate-100/80 dark:bg-slate-800/80 scale-[1.005]"
            : selectedFiles.length > 0
            ? "border-teal-600/60 bg-teal-50/20 dark:bg-teal-950/10"
            : "border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900/60 hover:border-slate-400 dark:hover:border-slate-600"
        } ${uploadMutation.isPending ? "pointer-events-none opacity-60" : ""}`}
      >
        {/* Esquinas Náuticas / Corner Accents */}
        <div className="absolute top-2 left-2 text-[10px] font-mono text-slate-400 dark:text-slate-600 select-none">
          +-- DOCK
        </div>
        <div className="absolute top-2 right-2 text-[10px] font-mono text-slate-400 dark:text-slate-600 select-none">
          PORT-01 --+
        </div>
        <div className="absolute bottom-2 left-2 text-[10px] font-mono text-slate-400 dark:text-slate-600 select-none">
          +-- ADM
        </div>
        <div className="absolute bottom-2 right-2 text-[10px] font-mono text-slate-400 dark:text-slate-600 select-none">
          SEC-PDF --+
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,application/pdf"
          onChange={handleFileChange}
          className="hidden"
          data-testid="file-input"
        />

        <div className="flex flex-col items-center text-center space-y-3.5">
          <div
            className={`p-3.5 rounded-md flex items-center justify-center transition-colors ${
              selectedFiles.length > 0
                ? "bg-teal-700 text-white"
                : "bg-slate-100 dark:bg-slate-800 text-[#0C1E32] dark:text-slate-200 border border-slate-200 dark:border-slate-700"
            }`}
          >
            {selectedFiles.length > 0 ? (
              <FileCheck className="w-6 h-6" />
            ) : (
              <UploadCloud className="w-6 h-6" />
            )}
          </div>

          <div className="space-y-1">
            <h3 className="font-semibold text-slate-900 dark:text-white text-base tracking-tight">
              {selectedFiles.length > 0
                ? `${selectedFiles.length} contrato(s) listo(s) para subir`
                : "Arrastra y suelta tu contrato PDF aquí"}
            </h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
              {selectedFiles.length > 0
                ? "Haz clic abajo para confirmar el procesamiento o agrega más archivos"
                : "o haz clic para explorar tus archivos (uno o varios PDF, máx. 25 MB c/u)"}
            </p>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
              <Anchor className="w-2.5 h-2.5" />
              PÓLIZAS BIMCO / NYPE / BILL OF LADING
            </span>
          </div>
        </div>
      </div>

      {/* Alerta de validación con shadcn Alert */}
      {validationError && (
        <Alert variant="destructive" className="border-red-300 dark:border-red-900 bg-red-50/80 dark:bg-red-950/30 text-red-900 dark:text-red-200 rounded-md">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="text-xs">{validationError}</AlertDescription>
        </Alert>
      )}

      {/* Lista de archivos seleccionados */}
      {selectedFiles.length > 0 && (
        <Card data-testid="selected-file-card" className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-md shadow-xs">
          <CardContent className="p-3.5 space-y-2">
            {selectedFiles.map((file) => (
              <div key={`${file.name}:${file.size}`} className="flex items-center justify-between gap-4">
                <div className="flex items-center space-x-3 overflow-hidden">
                  <div className="p-2 bg-slate-100 dark:bg-slate-800 text-[#0C1E32] dark:text-white rounded border border-slate-200 dark:border-slate-700 shrink-0">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div className="truncate">
                    <p className="font-medium text-xs text-slate-900 dark:text-white truncate">
                      {file.name}
                    </p>
                    <p className="text-[11px] font-mono text-slate-500">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  disabled={uploadMutation.isPending}
                  onClick={() => handleRemoveFile(file)}
                  title="Quitar archivo"
                  className="h-8 w-8 text-slate-500 hover:text-slate-900 dark:hover:text-white shrink-0"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ))}

            <div className="flex justify-end pt-1">
              <Button
                type="button"
                variant="default"
                disabled={uploadMutation.isPending}
                onClick={handleUpload}
                className="bg-[#0C1E32] hover:bg-[#152e4d] text-white font-medium text-xs h-8 px-3 rounded shadow-xs"
              >
                {uploadMutation.isPending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    <span>Subiendo...</span>
                  </>
                ) : (
                  <span>Confirmar y Procesar</span>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

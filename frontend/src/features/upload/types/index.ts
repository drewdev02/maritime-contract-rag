import { z } from "zod";
import type { ContractDocument } from "@/types/document";

const MAX_FILE_SIZE_MB = Number(import.meta.env.VITE_MAX_FILE_SIZE_MB) || 25;

export const uploadFileSchema = z.object({
  file: z
    .instanceof(File, { message: "Debe seleccionar un archivo válido." })
    .refine((file) => file.name.toLowerCase().endsWith(".pdf"), {
      message: "Solo se admiten contratos en formato PDF (.pdf).",
    })
    .refine((file) => file.size <= MAX_FILE_SIZE_MB * 1024 * 1024, {
      message: `El archivo no debe exceder los ${MAX_FILE_SIZE_MB} MB.`,
    }),
});

export type UploadFileFormValues = z.infer<typeof uploadFileSchema>;

export type UploadDocumentResponse = ContractDocument;

export interface BatchUploadItem {
  filename: string;
  document: UploadDocumentResponse | null;
  error: string | null;
}

export interface BatchUploadResponse {
  items: BatchUploadItem[];
  accepted: number;
  rejected: number;
}

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { BatchUploadResponse, UploadDocumentResponse } from "../types";

export const uploadDocumentRequest = async (file: File): Promise<UploadDocumentResponse> => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post<UploadDocumentResponse>("/documents/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return response.data;
};

export const uploadDocumentsBatchRequest = async (files: File[]): Promise<BatchUploadResponse> => {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const response = await apiClient.post<BatchUploadResponse>("/documents/upload-batch", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return response.data;
};

export const useUploadDocument = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (files: File[]) => uploadDocumentsBatchRequest(files),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });
};

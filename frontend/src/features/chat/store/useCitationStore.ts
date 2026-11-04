import { create } from "zustand";
import type { Citation } from "@/types/chat";

interface CitationState {
  activeCitation: Citation | null;
  isOpen: boolean;
  openCitation: (citation: Citation) => void;
  closeCitation: () => void;
  setOpen: (open: boolean) => void;
}

export const useCitationStore = create<CitationState>((set) => ({
  activeCitation: null,
  isOpen: false,
  openCitation: (citation: Citation) => set({ activeCitation: citation, isOpen: true }),
  closeCitation: () => set({ isOpen: false, activeCitation: null }),
  setOpen: (open: boolean) =>
    set((state) => ({
      isOpen: open,
      activeCitation: open ? state.activeCitation : null,
    })),
}));

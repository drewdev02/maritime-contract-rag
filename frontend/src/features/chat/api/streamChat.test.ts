import { describe, it, expect, vi, beforeEach } from "vitest";
import { streamContractQuestion } from "./streamChat";

describe("streamContractQuestion", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("parses tokens, meta, and done events successfully", async () => {
    const ssePayload = [
      'event: token\ndata: {"delta": "Hola "}\n\n',
      'event: token\ndata: {"delta": "mundo"}\n\n',
      'event: meta\ndata: {"citations": [{"chunk_id": "c1", "document_id": "d1", "document_name": "test.pdf", "page_number": 1, "snippet_text": "snip"}], "has_sufficient_evidence": true, "confidence_score": 0.88}\n\n',
      'event: done\ndata: {}\n\n',
    ].join("");

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(ssePayload));
        controller.close();
      },
    });

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      body: stream,
    } as unknown as Response);

    const tokens: string[] = [];
    let metaResult: unknown = null;
    let doneCalled = false;

    await streamContractQuestion(
      { query: "¿Hola?" },
      {
        onToken: (delta) => tokens.push(delta),
        onMeta: (meta) => {
          metaResult = meta;
        },
        onDone: () => {
          doneCalled = true;
        },
      }
    );

    expect(tokens.join("")).toBe("Hola mundo");
    expect(metaResult).toEqual({
      citations: [
        {
          chunk_id: "c1",
          document_id: "d1",
          document_name: "test.pdf",
          page_number: 1,
          snippet_text: "snip",
        },
      ],
      has_sufficient_evidence: true,
      confidence_score: 0.88,
    });
    expect(doneCalled).toBe(true);
  });

  it("handles HTTP error response properly", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      text: async () => "Internal server error occurred",
    } as unknown as Response);

    const onErrorSpy = vi.fn();

    await expect(
      streamContractQuestion(
        { query: "¿Test?" },
        {
          onToken: vi.fn(),
          onMeta: vi.fn(),
          onError: onErrorSpy,
        }
      )
    ).rejects.toThrow("Error 500");

    expect(onErrorSpy).toHaveBeenCalled();
  });
});

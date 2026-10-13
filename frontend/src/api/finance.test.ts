import { describe, expect, it, vi } from "vitest";

import { previewFinanceMailDraft } from "./finance";

describe("finance API errors", () => {
  it("reports an HTML error response without leaking a JSON parse exception", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response("<!doctype html><h1>Bad Request</h1>", {
      status: 400,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    }))));

    await expect(previewFinanceMailDraft("student_verification", 3, "csrf-preview-token"))
      .rejects.toThrow("Finanzanfrage fehlgeschlagen (HTTP 400; text/html; charset=utf-8)");
  });
});

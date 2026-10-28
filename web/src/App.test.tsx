import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

const META = {
  categories: ["Governing Law", "Anti-Assignment"],
  high_stakes: ["Governing Law", "Anti-Assignment"],
  disclaimer: "A review aid, not legal advice.",
  supported: [".pdf", ".docx", ".txt"],
};
const TEXT = "Governed by New York law. No assignment without consent.";
const DOC = {
  id: "d1", name: "supply.txt", status: "done", error: null, seconds: 0.1, scanned: false,
  findings: [
    { category: "Anti-Assignment", text: "No assignment without consent.", start: 26, end: 56,
      score: 0.9, location: "para. 1", high_stakes: true },
    { category: "Governing Law", text: "Governed by New York law.", start: 0, end: 25,
      score: 0.8, location: "para. 1", high_stakes: true },
  ],
  flags: [{ id: "governing-law-not-singapore", severity: "medium", measurable: true,
    title: "Governing law is not Singapore", explanation: "Foreign law.",
    evidence: [{ category: "Governing Law", start: 0, end: 25, location: "para. 1" }] }],
  missing: [],
  text: TEXT,
};
const PACK = { id: "p1", status: "done",
  documents: [{ ...DOC, n_findings: 2, flag_counts: { high: 0, medium: 1, low: 0 } }] };

beforeEach(() => {
  location.hash = "pack=p1";
  globalThis.fetch = vi.fn(async (url: string) => {
    const body = url.endsWith("/meta") ? META : url.includes("/documents/") ? DOC : PACK;
    return new Response(JSON.stringify(body), { status: 200 });
  }) as unknown as typeof fetch;
});

test("opens the pack, highlights quotes and moves through them with j", async () => {
  render(<App />);
  await screen.findByText("Governing law is not Singapore");
  expect(screen.getByText(/not legal advice/)).toBeTruthy();
  expect(document.querySelectorAll("mark")).toHaveLength(2);

  // j visits clause types in CUAD order, so Governing Law comes before Anti-Assignment.
  act(() => {
    fireEvent.keyDown(window, { key: "j" });
  });
  await waitFor(() => expect(document.querySelector("mark.active")?.textContent).toBe(
    "Governed by New York law.",
  ));
  act(() => {
    fireEvent.keyDown(window, { key: "j" });
  });
  await waitFor(() => expect(document.querySelector("mark.active")?.textContent).toBe(
    "No assignment without consent.",
  ));
});

test("t switches the theme", async () => {
  render(<App />);
  await screen.findByText("Governing law is not Singapore");
  act(() => {
    fireEvent.keyDown(window, { key: "t" });
  });
  expect(document.documentElement.getAttribute("data-theme")).toBe("light");
});

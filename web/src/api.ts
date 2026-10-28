import type { DocDetail, Meta, Pack } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    // FastAPI puts the reason in "detail"; I show that instead of a bare status code.
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

export const getMeta = () => fetch("/api/meta").then((r) => json<Meta>(r));

export function uploadPack(files: File[]): Promise<Pack> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return fetch("/api/packs", { method: "POST", body: form }).then((r) => json<Pack>(r));
}

export const getPack = (id: string) => fetch(`/api/packs/${id}`).then((r) => json<Pack>(r));

export const getDocument = (packId: string, docId: string) =>
  fetch(`/api/packs/${packId}/documents/${docId}`).then((r) => json<DocDetail>(r));

export const reportUrl = (packId: string, kind: "xlsx" | "html") =>
  `/api/packs/${packId}/report.${kind}`;

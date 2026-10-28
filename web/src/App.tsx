import { useCallback, useEffect, useMemo, useState } from "react";
import { getDocument, getMeta, getPack, uploadPack } from "./api";
import Contract from "./components/Contract";
import DocList from "./components/DocList";
import Findings from "./components/Findings";
import Upload from "./components/Upload";
import { step, visitOrder } from "./highlight";
import { applyTheme, loadTheme, nextTheme, type Theme } from "./theme";
import type { DocDetail, Meta, Pack } from "./types";

const THEME_NAME: Record<Theme, string> = { system: "System theme", light: "Light", dark: "Dark" };

// The pack id lives in the URL hash, so a refresh keeps the pack open.
const packFromHash = () => new URLSearchParams(location.hash.slice(1)).get("pack");

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [pack, setPack] = useState<Pack | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [doc, setDoc] = useState<DocDetail | null>(null);
  const [active, setActive] = useState(-1);
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const [help, setHelp] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => applyTheme(theme), [theme]);

  useEffect(() => {
    getMeta().then(setMeta).catch((e) => setError(e.message));
    const id = packFromHash();
    if (id) getPack(id).then(setPack).catch(() => (location.hash = ""));
  }, []);

  // Poll the pack while documents are still being reviewed.
  useEffect(() => {
    if (!pack || pack.status === "done") return;
    const timer = setTimeout(() => getPack(pack.id).then(setPack).catch(() => {}), 1500);
    return () => clearTimeout(timer);
  }, [pack]);

  // Open the first finished document once there is one.
  useEffect(() => {
    if (pack && !docId) {
      const first = pack.documents.find((d) => d.status === "done");
      if (first) setDocId(first.id);
    }
  }, [pack, docId]);

  useEffect(() => {
    if (!pack || !docId) return;
    setDoc(null);
    setActive(-1);
    getDocument(pack.id, docId).then(setDoc).catch((e) => setError(e.message));
  }, [pack?.id, docId]); // eslint-disable-line react-hooks/exhaustive-deps

  const order = useMemo(
    () => (doc && meta ? visitOrder(doc.findings, meta.categories) : []),
    [doc, meta],
  );

  const moveFinding = useCallback(
    (delta: 1 | -1) => {
      const pos = step(order.indexOf(active), order.length, delta);
      setActive(pos < 0 ? -1 : order[pos]);
    },
    [order, active],
  );

  const moveDocument = useCallback(
    (delta: 1 | -1) => {
      const done = pack?.documents.filter((d) => d.status === "done") ?? [];
      const pos = step(done.findIndex((d) => d.id === docId), done.length, delta);
      if (pos >= 0) setDocId(done[pos].id);
    },
    [pack, docId],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // Typing in a field should never trigger shortcuts.
      if (e.target instanceof HTMLInputElement || e.ctrlKey || e.metaKey || e.altKey) return;
      const actions: Record<string, () => void> = {
        j: () => moveFinding(1),
        k: () => moveFinding(-1),
        n: () => moveDocument(1),
        p: () => moveDocument(-1),
        t: () => setTheme((t) => nextTheme(t)),
        "?": () => setHelp((h) => !h),
        Escape: () => setHelp(false),
      };
      const act = actions[e.key];
      if (act) {
        e.preventDefault();
        act();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [moveFinding, moveDocument]);

  async function upload(files: File[]) {
    const p = await uploadPack(files);
    location.hash = `pack=${p.id}`;
    setDocId(null);
    setPack(p);
  }

  return (
    <>
      <header className="bar">
        <span className="name">ClauseScout</span>
        <span className="disclaimer">
          A review aid, not legal advice. Check every finding against the contract.
        </span>
        {pack && (
          <button
            onClick={() => {
              location.hash = "";
              setPack(null);
              setDocId(null);
              setDoc(null);
            }}
          >
            New pack
          </button>
        )}
        <button onClick={() => setTheme(nextTheme(theme))} title="Switch theme (t)">
          {THEME_NAME[theme]}
        </button>
        <button onClick={() => setHelp(!help)} aria-expanded={help} title="Keyboard shortcuts (?)">
          Shortcuts
        </button>
      </header>

      {error && (
        <p className="error" role="alert" style={{ padding: "0 20px" }}>
          {error}. Is the API running on port 8000?
        </p>
      )}

      {!pack && meta && <Upload supported={meta.supported} onUpload={upload} />}

      {pack && (
        <main className="review">
          <DocList pack={pack} current={docId} onOpen={setDocId} />
          {doc && meta ? (
            <>
              <Contract text={doc.text} findings={doc.findings} active={active} onPick={setActive} />
              <Findings doc={doc} categories={meta.categories} active={active} onPick={setActive} />
            </>
          ) : (
            <p className="muted" style={{ padding: 24 }}>
              {pack.status === "done" ? "Choose a contract." : "Reviewing the first contract..."}
            </p>
          )}
        </main>
      )}

      {help && (
        <div className="help" role="dialog" aria-label="Keyboard shortcuts">
          <p>
            <kbd>j</kbd> next quote, <kbd>k</kbd> previous quote
          </p>
          <p>
            <kbd>n</kbd> next contract, <kbd>p</kbd> previous contract
          </p>
          <p>
            <kbd>t</kbd> switch theme, <kbd>?</kbd> show or hide this
          </p>
        </div>
      )}
    </>
  );
}

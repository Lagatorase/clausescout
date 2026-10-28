import { reportUrl } from "../api";
import type { DocSummary, Pack } from "../types";

interface Props {
  pack: Pack;
  current: string | null;
  onOpen: (id: string) => void;
}

function status(d: DocSummary) {
  if (d.status === "failed") return <span className="error">Could not read: {d.error}</span>;
  if (d.status !== "done") {
    return <span className="muted">{d.status === "running" ? "Reviewing" : "Waiting"}</span>;
  }
  const f = d.flag_counts!;
  return (
    <span className="counts">
      <span style={{ color: "var(--high)" }}>{f.high} high</span>
      <span style={{ color: "var(--medium)" }}>{f.medium} medium</span>
      <span className="muted">{d.n_findings} quotes</span>
    </span>
  );
}

export default function DocList({ pack, current, onOpen }: Props) {
  const done = pack.documents.filter((d) => d.status === "done").length;
  return (
    <nav className="docs" aria-label="Contracts in this pack">
      <h2>
        Contracts <span className="muted">{done} of {pack.documents.length} reviewed</span>
      </h2>
      <ul>
        {pack.documents.map((d) => (
          <li key={d.id}>
            <button
              aria-current={d.id === current}
              disabled={d.status !== "done"}
              onClick={() => onOpen(d.id)}
            >
              <span className="doc-name">{d.name}</span>
              {status(d)}
              {d.scanned && <span className="error">Looks scanned: little text found</span>}
            </button>
          </li>
        ))}
      </ul>
      {done > 0 && (
        <div className="exports">
          <a href={reportUrl(pack.id, "xlsx")}>Download Excel</a>
          <a href={reportUrl(pack.id, "html")} target="_blank" rel="noreferrer">
            Open summary
          </a>
        </div>
      )}
    </nav>
  );
}

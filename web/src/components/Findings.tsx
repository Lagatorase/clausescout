import type { DocDetail } from "../types";

interface Props {
  doc: DocDetail;
  categories: string[];
  active: number;
  onPick: (index: number) => void;
}

const SEVERITY_NAME = { high: "High", medium: "Medium", low: "Low" };

export default function Findings({ doc, categories, active, onPick }: Props) {
  // Group finding indexes by clause type, in CUAD's category order.
  const byType = new Map<string, number[]>();
  doc.findings.forEach((f, i) => byType.set(f.category, [...(byType.get(f.category) ?? []), i]));
  const types = categories.filter((c) => byType.has(c));

  return (
    <aside className="panel" aria-label="Findings">
      <section>
        <h2>Playbook flags</h2>
        {doc.flags.length === 0 && <p className="muted">No flags for this contract.</p>}
        {doc.flags.map((fl) => (
          <div key={fl.id} className={`flag ${fl.severity}`}>
            <span className="sev">{SEVERITY_NAME[fl.severity]}</span> <strong>{fl.title}</strong>
            <p>{fl.explanation}</p>
            {fl.evidence.length > 0 && (
              <p className="muted">
                See{" "}
                {fl.evidence.map((e, k) => {
                  const idx = doc.findings.findIndex(
                    (f) => f.start === e.start && f.end === e.end && f.category === e.category,
                  );
                  // Two quotes on the same page get numbered, so the buttons differ.
                  const label = e.location || e.category;
                  const same = fl.evidence.slice(0, k).filter((o) => o.location === e.location);
                  return (
                    <button key={k} onClick={() => idx >= 0 && onPick(idx)}>
                      {same.length ? `${label} (${same.length + 1})` : label}
                    </button>
                  );
                })}
              </p>
            )}
          </div>
        ))}
      </section>
      <section>
        <h2>Clauses found</h2>
        {types.length === 0 && <p className="muted">No clauses found above the threshold.</p>}
        {types.map((c) => (
          <div key={c} className="type">
            <h3>
              {c}
              {doc.findings[byType.get(c)![0]].high_stakes && (
                <span className="stakes">high stakes</span>
              )}
            </h3>
            {byType.get(c)!.map((i) => {
              const f = doc.findings[i];
              return (
                <button
                  key={i}
                  className="quote"
                  aria-current={i === active}
                  onClick={() => onPick(i)}
                >
                  {f.text.length > 280 ? f.text.slice(0, 280) + "..." : f.text}
                  <br />
                  <span className="where">
                    {f.location || "no location"}, confidence {f.score.toFixed(2)}
                  </span>
                </button>
              );
            })}
          </div>
        ))}
      </section>
      <section className="missing">
        <h2>Not found</h2>
        <p className="muted">
          Not found is not the same as absent. Check the contract for these before relying on it.
        </p>
        <p>{doc.missing.join("; ")}</p>
      </section>
    </aside>
  );
}

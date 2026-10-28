import { useEffect, useMemo, useRef } from "react";
import { pieces } from "../highlight";
import type { Finding } from "../types";

interface Props {
  text: string;
  findings: Finding[];
  active: number;
  onPick: (index: number) => void;
}

export default function Contract({ text, findings, active, onPick }: Props) {
  const parts = useMemo(() => pieces(text.length, findings), [text, findings]);
  // PDF text keeps its line breaks. I show a single break as a space so lines reflow; the
  // length doesn't change, so every offset still matches the API's text.
  const shown = useMemo(() => text.replace(/(?<!\n)\n(?!\n)/g, " "), [text]);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Bring the selected quote into view in the middle of the page.
    const el = ref.current?.querySelector("mark.active");
    el?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  }, [active]);

  return (
    <article className="sheet" aria-label="Contract text">
      <div className="contract" ref={ref}>
        {parts.map((p) => {
          const chunk = shown.slice(p.start, p.end);
          if (p.covers.length === 0) return <span key={p.start}>{chunk}</span>;
          const isActive = p.covers.includes(active);
          return (
            <mark
              key={p.start}
              className={isActive ? "active" : undefined}
              title={p.covers.map((k) => findings[k].category).join(", ")}
              onClick={() => onPick(isActive ? active : p.covers[0])}
            >
              {chunk}
            </mark>
          );
        })}
      </div>
    </article>
  );
}

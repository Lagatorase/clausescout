import type { Finding } from "./types";

export interface Piece {
  start: number;
  end: number;
  // Indexes into the findings list of every finding that covers this piece of text.
  covers: number[];
}

/** Splits the text at every finding boundary, so overlapping quotes can all be highlighted. */
export function pieces(textLength: number, findings: Finding[]): Piece[] {
  const cuts = new Set([0, textLength]);
  findings.forEach((f) => {
    cuts.add(Math.max(0, Math.min(f.start, textLength)));
    cuts.add(Math.max(0, Math.min(f.end, textLength)));
  });
  const sorted = [...cuts].sort((a, b) => a - b);
  const out: Piece[] = [];
  for (let i = 0; i + 1 < sorted.length; i++) {
    const [start, end] = [sorted[i], sorted[i + 1]];
    const covers = findings.flatMap((f, k) => (f.start <= start && f.end >= end ? [k] : []));
    out.push({ start, end, covers });
  }
  return out;
}

/** The order findings are visited with j and k: clause type order first, then position. */
export function visitOrder(findings: Finding[], categories: string[]): number[] {
  const rank = (c: string) => {
    const i = categories.indexOf(c);
    return i < 0 ? categories.length : i;
  };
  return findings
    .map((_, i) => i)
    .sort((a, b) => rank(findings[a].category) - rank(findings[b].category) ||
      findings[a].start - findings[b].start);
}

/** Moves through a list with wrap-around; -1 means nothing selected yet. */
export function step(current: number, length: number, delta: 1 | -1): number {
  if (length === 0) return -1;
  if (current < 0) return delta === 1 ? 0 : length - 1;
  return (current + delta + length) % length;
}

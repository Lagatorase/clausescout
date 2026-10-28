// Shapes returned by the FastAPI backend (api/main.py).

export type Severity = "high" | "medium" | "low";

export interface DocSummary {
  id: string;
  name: string;
  status: "queued" | "running" | "done" | "failed";
  error: string | null;
  seconds: number | null;
  scanned: boolean;
  n_findings?: number;
  flag_counts?: Record<Severity, number>;
  high_stakes_found?: string[];
}

export interface Pack {
  id: string;
  status: "queued" | "running" | "done";
  documents: DocSummary[];
}

export interface Finding {
  category: string;
  text: string;
  start: number;
  end: number;
  score: number;
  location: string;
  high_stakes: boolean;
}

export interface Flag {
  id: string;
  severity: Severity;
  title: string;
  explanation: string;
  measurable: boolean;
  evidence: { category: string; start: number; end: number; location: string }[];
}

export interface DocDetail extends DocSummary {
  text: string;
  findings: Finding[];
  flags: Flag[];
  missing: string[];
}

export interface Meta {
  categories: string[];
  high_stakes: string[];
  disclaimer: string;
  supported: string[];
}

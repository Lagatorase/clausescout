"""How many CUAD gold clauses can be found word for word in the text I extract from the PDFs.

CUAD's gold spans come from its own plain-text versions of the contracts, but real contracts
arrive as PDFs. This measures how well my PDF extraction plus the grounding check preserves
the wording, by looking up every gold span of a split in the extracted PDF text.

Usage: python scripts/pdf_text_check.py --split val [--examples out.md]
"""

import argparse
import random
from pathlib import Path

from rapidfuzz import fuzz

from clausescout.data.cuad import load_split, pdf_path
from clausescout.data.documents import load_document
from clausescout.grounding.location import locate
from clausescout.grounding.verbatim import GroundingIndex


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="val")
    ap.add_argument("--examples", type=Path, help="write failing examples to this markdown file")
    ap.add_argument("--n-examples", type=int, default=40)
    args = ap.parse_args()

    total = found = multi_page = 0
    no_pdf, failures = [], []
    for c in load_split(args.split):
        path = pdf_path(c.id)
        if path is None:
            no_pdf.append(c.id)
            continue
        doc = load_document(path)
        index = GroundingIndex(doc.text)
        for cat, spans in c.labels.items():
            for s in spans:
                total += 1
                hit = index.find(s.text)
                if hit:
                    found += 1
                    loc = locate(doc.segments, *hit)
                    multi_page += loc.first != loc.last
                else:
                    failures.append((c.id, cat, s.text, doc.text))

    print(f"split {args.split}: {total} gold spans, {found} found verbatim ({found / total:.1%})")
    print(f"  found spans that cross a page break: {multi_page}")
    print(f"  contracts without a PDF: {len(no_pdf)}")

    if args.examples:
        # For each failing example I show the closest passage in the PDF text, so I can see why.
        rng = random.Random(0)
        sample = rng.sample(failures, min(args.n_examples, len(failures)))
        title = f"PDF text failures ({args.split}, {len(failures)} total, {len(sample)} shown)"
        lines = [f"# {title}\n"]
        for cid, cat, gold, text in sample:
            al = fuzz.partial_ratio_alignment(gold, text)
            lines += [f"## {cat} | {cid}\n", "Gold:\n", f"```\n{gold}\n```\n",
                      f"Closest in PDF text (score {al.score:.0f}):\n",
                      f"```\n{text[al.dest_start:al.dest_end]}\n```\n"]
        args.examples.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

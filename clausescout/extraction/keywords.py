"""The keyword and pattern baseline: hand-written search patterns for each clause type.

This is the floor every other method has to beat. I wrote the patterns from how these clauses
are usually drafted, before looking at any model output, and each one has a weight for how
sure a match makes me. A sentence that matches several patterns for a type gets a higher score
(1 minus the product of the misses), which gives the CUAD metrics a ranking to work with.

Most types return the whole matching sentence. Titles and dates return only the matched text,
because their gold spans are a few words long.
"""

from __future__ import annotations

import re

from clausescout.extraction.sentences import sentences
from clausescout.findings import Finding

_MONTH = (r"(?:January|February|March|April|May|June|July|August|September|October|November"
          r"|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?")
DATE = (rf"(?:{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}"
        rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?{_MONTH},?\s+\d{{4}}"
        rf"|\d{{1,2}}/\d{{1,2}}/\d{{2,4}})")
_NOT_NON = r"(?<!non-)(?<!non )(?<!non)"

# Clause type to (pattern, weight) pairs, matched case-insensitively against each sentence.
PATTERNS: dict[str, list[tuple[str, float]]] = {
    "Parties": [
        (r"\bby and (?:between|among)\b", 0.8),
        (r"\b(?:between|among)\b.{0,200}\band\b", 0.4),
        (r"\(\s*(?:the\s+)?[\"'][A-Z][\w .&-]{1,40}[\"']\s*\)", 0.5),
    ],
    "Effective Date": [
        (r"\beffective date\b", 0.6),
        (r"\b(?:effective|shall become effective) (?:as of|on)\b", 0.7),
    ],
    "Expiration Date": [
        (r"\b(?:initial )?term of this agreement\b", 0.5),
        (r"\b(?:continue|remain) in (?:full )?(?:force and )?effect (?:until|for)\b", 0.7),
        (r"\bexpire[sd]?\b", 0.5),
        (r"\binitial term\b", 0.5),
    ],
    "Renewal Term": [
        (r"\bautomatically (?:be )?(?:renew|extend)", 0.8),
        (r"\brenewal (?:term|period)s?\b", 0.6),
        (r"\bsuccessive\b.{0,40}\b(?:year|month|term|period)s?\b", 0.6),
    ],
    "Notice Period To Terminate Renewal": [
        (r"\bnon-?renewal\b", 0.7),
        (r"\b(?:intention|intent|election|decision) not to (?:renew|extend)\b", 0.8),
        (r"\bnotice\b.{0,120}\bprior to the (?:end|expiration)\b.{0,40}\bterm\b", 0.6),
    ],
    "Governing Law": [
        (r"\bgoverned by\b.{0,80}\blaws?\b", 0.9),
        (r"\bconstrued (?:and enforced )?in accordance with\b.{0,60}\blaws?\b", 0.9),
        (r"\blaws of the (?:state|commonwealth|province|republic|people's republic)\b", 0.6),
        (r"\bgoverning law\b", 0.5),
    ],
    "Most Favored Nation": [
        (r"\bmost favou?red\b", 0.9),
        (r"\b(?:no less|at least as|not less) favou?rable\b", 0.6),
        (r"\b(?:lower|better|more favou?rable) (?:price|terms)\b.{0,80}\b(?:offer|grant)", 0.5),
    ],
    "Non-Compete": [
        (r"\bnon-?compet", 0.8),
        (r"\b(?:shall|will|may) not\b.{0,120}\bcompet(?:e|ing|itive)\b", 0.7),
        (r"\bengage in\b.{0,80}\b(?:competing|competitive|compete)\b", 0.6),
    ],
    "Exclusivity": [
        (rf"{_NOT_NON}\bexclusive (?:right|distributor|supplier|licen[cs]e|basis|provider|agent"
         r"|reseller|partner|manufacturer|dealer)", 0.7),
        (rf"{_NOT_NON}\bexclusively\b", 0.6),
        (r"\bsole and exclusive\b", 0.6),
        (r"\b(?:shall|will) not\b.{0,80}\b(?:appoint|purchase from|sell to)\b.{0,60}\bother\b",
         0.5),
    ],
    "No-Solicit Of Customers": [
        (r"\bsolicit\w*\b.{0,100}\b(?:customers?|clients?|accounts)\b", 0.7),
        (r"\b(?:customers?|clients?)\b.{0,60}\bsolicit", 0.5),
    ],
    "Competitive Restriction Exception": [
        (r"\bnotwithstanding (?:the foregoing|anything)\b.{0,250}"
         r"\b(?:compet\w*|exclusiv\w*|solicit\w*)", 0.6),
        (r"\bshall not (?:be deemed to )?(?:prohibit|restrict|prevent|limit)\b", 0.4),
    ],
    "No-Solicit Of Employees": [
        (r"\bsolicit\w*\b.{0,100}\b(?:employ\w*|personnel|staff|consultants?)\b", 0.7),
        (r"\b(?:hire|employ|engage)\b.{0,80}\bemployees? of the other\b", 0.7),
    ],
    "Non-Disparagement": [
        (r"\bdisparag", 0.9),
        (r"\b(?:negative|derogatory|defamatory)\b.{0,40}\bstatements?\b", 0.6),
    ],
    "Termination For Convenience": [
        (r"\bterminat\w*\b.{0,120}\bfor (?:any reason|no reason|convenience)\b", 0.8),
        (r"\bterminat\w*\b.{0,120}\bwithout cause\b", 0.8),
        (r"\bterminat\w*\b.{0,60}\bat any time\b.{0,80}\bnotice\b", 0.6),
    ],
    "Rofr/Rofo/Rofn": [
        (r"\bright of first (?:refusal|offer|negotiation)\b", 0.9),
        (r"\bfirst right (?:of|to) (?:refusal|negotiate|purchase|offer)\b", 0.8),
        (r"\bright to match\b", 0.6),
    ],
    "Change Of Control": [
        (r"\bchange (?:of|in) (?:control|ownership)\b", 0.9),
        (r"\b(?:merger|consolidation|reorgani[sz]ation)\b", 0.4),
        (r"\b(?:all or )?substantially all of (?:its|the) (?:assets|business|stock)\b", 0.5),
    ],
    "Anti-Assignment": [
        (r"\b(?:may|shall|will|can) not\b.{0,60}\bassign", 0.8),
        (r"\bassign\w*\b.{0,120}\b(?:prior written consent|without the (?:prior )?consent)\b",
         0.8),
        (r"\bnot be assignable\b", 0.8),
        (r"\bnon-?assignable\b", 0.6),
    ],
    "Revenue/Profit Sharing": [
        (r"\broyalt(?:y|ies)\b", 0.6),
        (r"\b(?:revenue|profit)s?[- ]shar", 0.8),
        (r"\b(?:percent(?:age)?|%) of (?:the )?(?:net |gross )?(?:revenue|sales|profit|receipts"
         r"|income)", 0.7),
    ],
    "Price Restrictions": [
        (r"\b(?:shall|may|will) not\b.{0,60}\b(?:increase|raise|change|adjust)\b.{0,30}\bprices?",
         0.7),
        (r"\bprice (?:increase|adjustment)s?\b.{0,80}\b(?:not exceed|limited to|no more than)\b",
         0.7),
        (r"\bprices?\b.{0,40}\b(?:fixed|firm)\b", 0.4),
    ],
    "Minimum Commitment": [
        (r"\bminimum (?:purchase|order|quantity|volume|commitment|annual|monthly|guarantee)",
         0.8),
        (r"\b(?:purchase|order|buy)\b.{0,40}\b(?:no less|not less|at least)\b", 0.6),
    ],
    "Volume Restriction": [
        (r"\b(?:maximum|not to exceed|shall not exceed|up to)\b.{0,60}\b(?:units|users|copies"
         r"|installations|seats|volume|quantit)", 0.6),
        (r"\bvolume (?:limit|restriction|cap)", 0.8),
    ],
    "Ip Ownership Assignment": [
        (r"\bhereby (?:irrevocably )?(?:assigns?|transfers?|conveys?)\b.{0,120}"
         r"\b(?:right, title|intellectual property|all rights|ownership)\b", 0.8),
        (r"\bshall (?:be|become|remain) the (?:sole and )?(?:exclusive )?property of\b", 0.5),
        (r"\bworks? made for hire\b", 0.8),
        (r"\bshall (?:solely |exclusively )?own\b.{0,80}\b(?:intellectual property|inventions"
         r"|developments|improvements|work product)\b", 0.6),
    ],
    "Joint Ip Ownership": [
        (r"\bjointly (?:own|owned)\b", 0.9),
        (r"\bjoint(?:ly)? (?:ownership|owners)\b", 0.8),
        (r"\bco-?own", 0.7),
    ],
    "License Grant": [
        (r"\bhereby grants?\b.{0,150}\blicen[cs]e\b", 0.9),
        (r"\bgrants?\b.{0,80}\b(?:right and )?licen[cs]e to\b", 0.7),
        (r"\blicen[cs]e grant\b", 0.6),
    ],
    "Non-Transferable License": [
        (r"\bnon-?transferable\b", 0.8),
        (r"\bnon-?sub-?licensable\b", 0.7),
        (r"\bwithout the right to sub-?licen[cs]e\b", 0.8),
    ],
    "Affiliate License-Licensor": [
        (r"\blicensor\b.{0,40}\b(?:and|or) its affiliates\b.{0,80}\bgrant", 0.5),
        (r"\baffiliates of (?:the )?licensor\b", 0.4),
    ],
    "Affiliate License-Licensee": [
        (r"\blicensee\b.{0,40}\b(?:and|or) its affiliates\b", 0.5),
        (r"\b(?:sub-?licen[cs]e|extend)\b.{0,60}\b(?:to )?(?:its|their) affiliates\b", 0.5),
    ],
    "Unlimited/All-You-Can-Eat-License": [
        (r"\bunlimited (?:number|use|copies|users|access|quantit)", 0.8),
        (r"\benterprise[- ]wide\b", 0.6),
        (r"\bwithout (?:limitation|limit) (?:as to|on) (?:the )?(?:number|quantity)\b", 0.7),
    ],
    "Irrevocable Or Perpetual License": [
        (r"\birrevocabl[ey]\b", 0.7),
        (r"\bperpetu(?:al|ity)\b", 0.7),
    ],
    "Source Code Escrow": [
        (r"\bescrow\b", 0.8),
        (r"\bsource code\b", 0.4),
    ],
    "Post-Termination Services": [
        (r"\b(?:upon|after|following) (?:the )?(?:termination|expiration)\b.{0,150}"
         r"\b(?:continue to|transition|wind[- ]down|sell[- ]off|return|deliver)\b", 0.6),
        (r"\btransition (?:services|period|assistance)\b", 0.7),
        (r"\bsurvive\w*\b.{0,40}\b(?:termination|expiration)\b", 0.4),
    ],
    "Audit Rights": [
        (r"\baudit", 0.7),
        (r"\b(?:inspect|examin)\w*\b.{0,80}\b(?:books|records|accounts)\b", 0.7),
    ],
    "Uncapped Liability": [
        (r"\b(?:shall not apply|does not apply|do not apply|shall not limit|not be limited)\b"
         r".{0,150}\b(?:indemnif\w*|gross negligence|wil(?:l)?ful|fraud|confidential\w*)", 0.6),
        (r"\b(?:except|excluding|other than)\b.{0,40}\b(?:for )?(?:breach of confidential\w*"
         r"|indemnification obligations|gross negligence|wil(?:l)?ful misconduct)", 0.5),
    ],
    "Cap On Liability": [
        (r"\b(?:aggregate|total|maximum|cumulative|entire) liability\b.{0,150}"
         r"\b(?:exceed|limited to|not to exceed|in excess of)\b", 0.9),
        (r"\bin no event shall\b.{0,150}\bliab", 0.7),
        (r"\blimitation of liability\b", 0.5),
        (r"\b(?:consequential|incidental|indirect|special|punitive) damages\b", 0.5),
    ],
    "Liquidated Damages": [
        (r"\bliquidated damages\b", 0.9),
        (r"\b(?:as a|not a) penalty\b", 0.6),
        (r"\blate (?:payment )?(?:fee|charge|penalt)", 0.6),
        (r"\btermination fee\b", 0.5),
    ],
    "Warranty Duration": [
        (r"\bwarrant\w*\b.{0,150}\b(?:for a period of|\(\d+\) (?:days|months|years)"
         r"|months? (?:from|after|following))", 0.7),
        (r"\bwarranty period\b", 0.7),
    ],
    "Insurance": [
        (r"\binsurance\b", 0.7),
        (r"\b(?:additional )?insureds?\b", 0.6),
    ],
    "Covenant Not To Sue": [
        (r"\bcovenants? not to sue\b", 0.9),
        (r"\b(?:shall|will|agrees? to) not\b.{0,60}\b(?:sue|bring (?:any )?(?:claim|action|suit)"
         r"|contest|challenge)\b", 0.6),
    ],
    "Third Party Beneficiary": [
        (r"\bthird[- ]party beneficiar", 0.9),
        (r"\bnothing in this agreement\b.{0,120}\bconfer\w*\b.{0,80}\b(?:any person|third)\b",
         0.7),
    ],
}

_COMPILED = {
    cat: [(re.compile(p, re.IGNORECASE | re.DOTALL), w) for p, w in pats]
    for cat, pats in PATTERNS.items()
}
_TITLE = re.compile(r"^[ \t]*([A-Z][A-Z0-9 ,&'./()-]{2,120}?\b(?:AGREEMENT|CONTRACT|LICENSE"
                    r"|LICENCE|AMENDMENT|ADDENDUM|MEMORANDUM|ARRANGEMENT)\b[A-Z0-9 ,&'./()-]*)$",
                    re.MULTILINE)
_DATE = re.compile(DATE, re.IGNORECASE)
# Titles, parties and the agreement date are on the first page.
OPENING_CHARS = 3000


class KeywordExtractor:
    name = "keywords"

    def extract(self, contract_id: str, text: str) -> list[Finding]:
        found: list[Finding] = []

        def add(cat, start, end, score):
            found.append(Finding(contract_id, cat, text[start:end], score, start, end, self.name))

        # Titles: an all-caps line on the opening page that names a kind of agreement.
        for k, m in enumerate(_TITLE.finditer(text[:OPENING_CHARS])):
            add("Document Name", m.start(1), m.end(1), max(0.9 - 0.3 * k, 0.1))

        # Agreement date: dates on the opening page, the first one being the likeliest.
        for k, m in enumerate(_DATE.finditer(text[:OPENING_CHARS])):
            add("Agreement Date", m.start(), m.end(), max(0.8 - 0.2 * k, 0.1))

        for start, end in sentences(text):
            passage = text[start:end]
            for cat, pats in _COMPILED.items():
                misses = 1.0
                for pat, weight in pats:
                    if pat.search(passage):
                        misses *= 1 - weight
                if misses < 1.0:
                    score = 1 - misses
                    # Parties are named at the start, so I trust matches there more.
                    if cat == "Parties" and start > OPENING_CHARS:
                        score *= 0.3
                    add(cat, start, end, score)
        return found

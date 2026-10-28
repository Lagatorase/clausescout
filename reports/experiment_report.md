# Experiment report (validation)

All numbers in this report come from the 62 validation contracts. CUAD's 102 test contracts
are untouched until the final configuration has been chosen.

## How the final configuration is chosen

I wrote this rule down before comparing any method other than the keyword baseline, so the
choice can't drift towards whichever result looks best afterwards.

1. The final configuration is the method with the highest mean contract-level F2 over the eight
   high-stakes clause types (Cap On Liability, Uncapped Liability, Termination For Convenience,
   Change Of Control, Anti-Assignment, Exclusivity, Non-Compete, Governing Law) on validation.
   F2 counts recall twice as much as precision, because a missed clause in due diligence costs
   more than an extra clause to read.
2. If the top methods are within run-to-run noise, or their 95% bootstrap intervals overlap, I
   prefer the one that runs fully locally, then the cheaper one, then the faster one.

Method 5 (a hosted LLM through the Anthropic API) is not yet run. It costs money, so I left it
out, and it is not part of this choice.

## Results

To be filled in from `reports/validation_tables.md` once the runs finish.

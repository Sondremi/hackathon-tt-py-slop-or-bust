# Judging Brief

## 3-Minute Demo Structure

1. Problem framing (20s)
- The task is to build a Python translator pipeline under strict anti-cheating rules.
- We optimized for deterministic correctness first, then maintainability and explainability.

2. Architecture (45s)
- Immutable wrapper layer handles HTTP + orchestration only.
- Generated implementation layer contains all portfolio math.
- Translator entrypoint writes implementation into the scaffold output on each run.

3. Financial behavior (60s)
- Activity replay model per symbol:
  - BUY/SELL average-cost accounting
  - Short-open and buy-to-cover handling
  - Fees/dividends integration
- Endpoint outputs derived from replay state:
  - performance, investments, holdings, details, dividends, report

4. Validation discipline (35s)
- Repeatable loop:
  - translate
  - full API tests
  - code quality scoring
  - rule-breach checks
- Show latest metrics from `tools/judge_ready_report.sh`.

5. Trade-offs (20s)
- Prioritized reliability and explainability in hackathon constraints.
- Chose deterministic implementation generation over broad, opaque transpilation.

## Judge Q&A Cheat Sheet

- Why not modify wrapper?
  - Rules require wrapper to remain byte-identical. Domain logic must stay in implementation.

- How do you prevent hidden cheating vectors?
  - We run mandatory rule-breach checks after major changes and before submission.

- How is correctness proven?
  - Full integration suite against API contracts, not only unit snippets.

- How did you improve after passing tests?
  - Reduced complexity through function decomposition and improved maintainability/documentation for judge explainability.

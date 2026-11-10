# PR7 independent review

Reviewer: `/root/reviewer_pr7`. Read-only source/evidence inspection; no tests executed or repeated. CodePolicyEvaluator allowed reviewed source paths and this report. Guardrails and KB were not edited. Existing MCP evidence was used; live hook activation is not attested.

## Findings sent to host

- P2 — `prepare_model.py`: `etag_timeout=10` only bounds metadata requests; missing-file transfer/overall execution also needs a bound or a documented bounded subprocess entry point.
- P2 — `rag.py`: `build_index(timeout=300)` checks elapsed time after encoding; it cannot interrupt a stalled encoder. Treat it as a soft budget; use an external process deadline for a hard limit.
- P2 — `rag.py`: reject manifests missing the exact required model file set; accepting arbitrary or empty `hashes` delays incomplete-file detection until loading.
- P2 — `mcp_server/README.md`: the statement that each search scans/rebuilds is obsolete. Document explicit index build, in-memory reuse and manual rebuild after corpus changes.

## Verified evidence

- Original index contains 32 chunks. Its model identifier/revision matches the offline model configuration.
- Saved ten-query baseline: Hit@5=0, MRR@5=0. Saved semantic MCP run: Hit@5=0.9, MRR@5=0.85. Query 8 gold rank=2; query 2 gold is absent; the other eight gold ranks are 1.
- Query 2 nevertheless retrieves the validation ADR, which can support an answer about Pydantic. Retrieval gold-hit failure and answer failure must be evaluated separately.
- Query 10 source `Concepts/Git Ingestion Verification.md` contains only confirmation of PR3 integration. Do not infer detailed test steps solely from that source.
- Source retains `search_notes(query: str) -> list[str]`. Search loads the ready index and only embeds query text; model is cached across encoder instances in the process. Per-note read policy is checked before result exposure.
- The handoff ledger currently records Planner to Coder. Host must record subsequent actual outcomes rather than claim a completed Coder/Reviewer chain prematurely.

## Host follow-up

Host reports a 60-second subprocess bound around missing-file downloads and exact nine-file manifest validation, and will replace the obsolete README behavior and disclose the soft build budget. These follow-up reports are distinguished from this source snapshot; no checks were repeated.

For answer evaluation, the proposed disclosed rubric is appropriate: 2=complete and supported by retrieved sources, 1=supported but partial, 0=absent or incorrect. Query 2 can receive 2 using the retrieved validation ADR. Query 10 should receive 1 with an explicit statement that the note confirms PR3 integration but contains no command/status/commit evidence. The resulting proposed 19/20 versus ten baseline abstentions (0/20) is an agent/source assessment, not a blind independent generation benchmark. The host must save the actual answers and their source references before claiming that score as completed evidence.

Acceptance remains conditional on the documentation updates, actual answer artifact and actual test outcome. No additional code defect was confirmed in the inspected scope.

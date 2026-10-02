# Presentation demonstration runbook

Use the existing PowerPoint. Open the GitHub sample from slide 10, show its documents and saved Azure report, and return to the slides for the execution model. No dashboard or live dispatch is required for this flow.

## Before the session

- Open the [sample walkthrough](demo-walkthrough.md) and [Azure report](../samples/azure-report/report.md) in browser tabs. Check the links on slides 10 and 12.
- Keep the source ZIP and PDF available in case GitHub or the presentation viewer is unavailable. The ZIP includes the documents and saved report.
- Introduce this as saved evidence for docops-live-20261002094646. The Blob files were last modified on October 2, 2026 at 09:47:31 UTC.
- For an optional live run, finish [Azure setup](azure-setup.md), verify credentials and rehearse first. Keep the Routine schedule disabled.

## 17:00–20:00: Show the documents and result

Click **Open sample on GitHub** on slide 10. Follow the walkthrough:

1. Show the English index and its missing deploy.md target.
2. Compare the English and Korean setup snippets. Explain the recorded source baseline.
3. Click **Open the Azure report**. Point to the matching file paths and two findings.

Suggested line: “These are the files we asked the worker to check. Here is the report from an actual Azure execution. One internal link is broken, and one translated page needs review.”

Continue: “The agent chose the checks. The worker inspected the fixed snapshot and wrote these findings. It did not translate or change the files.”

## 20:00–24:00: Explain completion

Return to slide 11. Separate invocation completion, worker execution and application completion. A matching committed report establishes the application result. This October 2 report does not capture its Job execution ID; do not infer one from nearby execution times.

Slide 12 summarizes the findings and links directly to the same public report. The [September 30 recording](../samples/cloud-validation/provenance.json) separately captures a request-linked worker execution. Do not mix its identifiers with the October 2 report.

## 24:00–27:00: Connect the result to the architecture

Use slide 9 or the walkthrough's responsibility table if a recap helps. The Routine starts an invocation, the agent requests allowed work, Python validates it, the queue carries it, the Job executes it, and Blob Storage holds the report. Queue delivery can repeat. The sample deduplicates a logical result, not every possible execution.

## 27:00–29:00: Explain the boundary

Slide 13 shows a prepared invalid request with run_shell. The Python contract rejects this action before submission. Label this as a local validation example; the successful saved report is not evidence of this rejection.

Return to slide 14 by minute 29. If behind, shorten the architecture recap. Preserve the input/result comparison and the distinction between a saved result and a live run.

## Optional Q&A material

The [execution viewer](../demo-viewer/README.md) supports saved September 30 evidence, actual local Python execution, and Azure dispatch/read-only observation with server-side credentials. These are different modes. A restored observation is not a fresh Azure query.

For a current Azure observation, **Open in Azure** opens the report container. Follow the displayed reports/<request-id>/report.json path. It requires an account and directory with access. This private source link is an optional presenter bookmark; the public GitHub report works without Azure access.

If observation fails, retain the request ID and last verified evidence. An observer error does not establish Job failure. Read the existing request before considering another dispatch. Never present an earlier saved success as the result of a pending live request.

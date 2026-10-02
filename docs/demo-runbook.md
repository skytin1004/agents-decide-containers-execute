# Presentation demonstration runbook

Use the PowerPoint. Show **sample documents, then the resulting GitHub Issue**, and return to the architecture. The main walkthrough takes about three minutes.

## Before the session

- Open the [sample walkthrough](demo-walkthrough.md) and [Issue #1](https://github.com/skytin1004/agents-decide-containers-execute/issues/1) in browser tabs. Check slides 10 and 12.
- Keep the source ZIP and PDF available. The source includes [an offline Issue copy](../samples/issue-demo/issue.md).
- Introduce Issue #1 as the saved result of actual Azure request `docops-gh-37010261060`, published October 2, 2026. Opening it does not invoke Azure.
- For an optional new live run, follow [Issue demo setup](issue-demo.md). Start the workflow before explaining the architecture. Show its new Issue only after publication succeeds.

## 17:00–20:00: Inputs and outcome

Click **Open sample on GitHub** on slide 10. Show the missing deployment link, then compare the English and Korean setup snippets. Click **Open the Issue on GitHub** and point to its two findings and review checkboxes. Keep execution evidence collapsed.

> These are the documents we asked the worker to check. Here is the GitHub Issue created from an actual Azure execution. It identifies one broken link and one translated page that needs review.
> The agent chose the checks. The container ran them, and the publisher put the verified findings where the maintainer can act on them. The files have not been changed.

## 20:00–24:00: Completion

Return to slide 11. Routine dispatch means the invocation was accepted. Worker commitment means a matching report is available. Issue publication means the result is available in GitHub. A GitHub failure can leave a valid Azure report without an Issue. A mismatch between requested and executed checks prevents publication.

## 24:00–27:00: Reviewable findings

Slide 12 summarizes the same two findings and links to Issue #1. The translation check compares source baselines; it does not assess language quality or generate a translation. Slide 9 ends at Blob Storage. GitHub Actions reads that completed result and publishes it.

## 27:00–29:00: Execution boundary

Slide 13 explains the separate prepared `run_shell` rejection example. Python rejects it before queue submission. The successful Issue is not evidence that this separate invalid request was run. Reach slide 14 by minute 29.

## Optional Q&A

Expand **Execution evidence** for the request, report hash and workflow. The [saved artifact files](../samples/issue-demo/README.md) retain the result after workflow artifacts expire. They do not contain a Job execution ID or a model reasoning trace.

The [viewer](../demo-viewer/README.md), Azure Portal and raw logs are optional. Viewer/direct Routine dispatch produces the Blob report. Use `publish-existing` with the same request ID to publish that result. Keep the Routine schedule disabled.

If a live workflow fails or takes too long, say so and show the saved Issue as a previous result. Re-running a completed workflow reads the committed report and reuses the existing Issue. Local rehearsal uses Python and SQLite without an LLM, Azure or GitHub publication.

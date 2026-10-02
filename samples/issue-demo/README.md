# Verified Azure result published as a GitHub Issue

**[Open Issue #1](https://github.com/skytin1004/agents-decide-containers-execute/issues/1)** · [Offline Issue copy](issue.md) · [Workflow](https://github.com/skytin1004/agents-decide-containers-execute/actions/runs/37010261060)

The workflow for commit `8c4336899f11d306c1b80dfb8f6b95b6065084ed` manually dispatched the Foundry Routine, read completed state and a matching report from Azure Blob Storage, validated both requested checks, and created Issue #1 as `github-actions[bot]` on October 2, 2026 at 13:02:43 UTC.

| Evidence | Purpose |
| --- | --- |
| [invocation.json](invocation.json) | Observed dispatch acceptance; returned run ID was not captured |
| [request-state.json](request-state.json) | Committed application state and original request digest |
| [report.json](report.json) | Raw report bytes downloaded by the workflow |
| [publication.json](publication.json) | Creation receipt, Issue URL and report SHA-256 |
| [retry-publication.json](retry-publication.json) | Attempt 2 reused Issue #1 with the same request and report |
| [issue.md](issue.md) | Readable saved copy for offline presentation |

Request: `docops-gh-37010261060`. Report SHA-256: `8b26a09ee1b62a705b9d120e26456a77562f73d52476ebbad4bbad0aec215c24`. These files were downloaded from the successful workflow artifact. The report has two findings: `docs/en/index.md:6` points to missing `deploy.md`, and `docs/ko/setup.md` needs source-baseline review.

This is saved evidence of an actual Azure execution and GitHub publication. It does not contain a Job execution ID or model reasoning trace. The fixture consistency check does not independently attest the cloud worker image. The earlier October 2 `docops-live-20261002094646` report and September 30 `docops-both-001` recording are separate requests.

An earlier Issue workflow request, `docops-gh-37009599145`, selected only `check_links` despite a two-check request. The publisher rejected the mismatch and created no Issue. The caller's prompt was clarified and a new request ID used; the earlier result was not overwritten. This demonstrates the publication guard and why allowlisted actions alone do not establish intent accuracy.

The same workflow run was rerun as attempt 2. It read the already completed request, skipped a new Routine dispatch, and reused Issue #1 at 13:03:57 UTC. The report and request-state bytes matched attempt 1. The repository contained one Issue after this test. This is an observed retry result, not an exactly-once guarantee under deletion, edited markers, or failures outside the tested path.

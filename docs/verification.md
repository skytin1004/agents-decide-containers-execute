# Verification record

Original cloud validation: September 30, 2026. Publication checks and saved-report retrieval: October 2, 2026. This is a record of observed behavior, not a service reliability guarantee.

## Environment

| Item | Verified configuration |
| --- | --- |
| Region | East US |
| Hosted agent | Python 3.13, agent version 1, active route |
| Model deployment | gpt-4.1-mini, model version 2025-04-14 |
| Worker | Container Apps event-driven Job, 0.25 vCPU / 0.5 GiB, 1 message per execution |
| Worker image digest | sha256:8c0d37ff4ed020f0f8a80638237c742d10a4989533320d92f9c952fc04db225b |
| Local verification | Windows, Python 3.12.6 |
| Dependency set | requirements-cloud.txt and requirements-worker.txt |

The dependency set installed successfully. Both Bicep templates compiled, the ACR build succeeded, and the foundation and Job deployments succeeded. The hosted agent has its own instance identity; storage roles were assigned to that identity and the worker identity separately. Personal subscription and tenant details are deliberately omitted from these public records.

## Observed cloud results

| Scenario | Request / evidence | Outcome |
| --- | --- | --- |
| Manual dispatch of a disabled Routine | docops-both-001; samples/cloud-validation/both-checks.json and provenance.json | Both actions completed; one broken link and one stale translation baseline |
| Link-only request through the real model | docops-links-001; samples/cloud-validation/links-only.json | Only check_links selected; one finding |
| Greeting through the real model | samples/cloud-validation/no-action.json | No submit_checks call in the observed response |
| Resubmit the completed request through the agent | docops-both-001; samples/cloud-validation/duplicate.json | Tool returned duplicate with existing_status completed |

The successful Routine run was 15c3749d-60e0-4097-bd6d-fad0110b19f6. It finished at 12:40:22 UTC. Worker execution docops-worker-k2r6j logged both actions and committed completion at 12:40:54 UTC. The matching report contains finding_count 2. See provenance.json for the request-state ETag, timestamp, and image digest.

These timings describe one run; they are not a benchmark. A successful container exit alone does not establish a report for a particular request. The evidence includes the report and matching worker log.

## Initial outcome and correction

An earlier cloud request with ID docops-demo-001 completed with only check_links. That record was preserved; it must not be used as evidence of both checks succeeding. The same ID remains bound to its original one-action payload in that validation account.

The helper's default prompt was made explicit: run both named checks in one submission. A new request, docops-both-001, then produced the expected two-action result. The operator's attempt to retrieve the original Routine response returned session_not_accessible (403), so the precise cause of the earlier one-action selection is unconfirmed. It is not presented as a diagnosed service defect.

The local sample's docops-demo-001 is a different run in a separate SQLite store and correctly selects both actions. Fresh Azure examples use a generated ID. Schema validation constrains allowed operations; it does not prove that a model selected every semantically required action.

## Local tests

The following command passed all 20 tests:

~~~powershell
python -m unittest discover -s tests -v
~~~

Coverage includes invalid operations and fields, fixed repository and ID restrictions, action-order canonicalization, exact fixture findings, CRLF hash normalization, concurrent submissions, competing claims, expired-owner fencing, duplicate completion, conflict rejection, injected retry, and local poison handling. The documented CLI demo and intentional rejection/failure commands were also checked from a clean package extraction.

The source ZIP was extracted into a fresh directory and installed in a new virtual environment. Its exported report matched samples/expected-report.json. A wheel was also installed and the demo run from outside the source directory with Python isolated mode, verifying that the fixture is included in the installed package. This check exposed an unsupported console punctuation character under Windows code page 949; the CLI banner now uses ASCII punctuation.

The GitHub Actions workflow specifies Windows/Linux and Python 3.11/3.13. It installs the worker SDK dependencies so the Azure-mocked viewer tests also run. Remote results are available in the repository's Actions tab; local results alone do not establish every matrix combination.

## October 2 publication checks

All 32 checkout tests passed with the repository virtual environment: 20 core tests and 12 viewer tests, with no skipped tests. Viewer coverage includes read-only observation without dispatch, report/request matching, retained local output, recorded timestamps, recovery after observer errors and validated Azure Portal links. These tests do not call Azure.

The [saved Azure report](../samples/azure-report/README.md) for docops-live-20261002094646 was downloaded through authenticated read-only access. Its original JSON and Markdown bytes are included, with SHA-256 hashes and the Blob modification time. This retrieval did not dispatch a new execution. A Job execution ID was not captured for this request. The September 30 request-linked worker log above remains a separate record.

## Not established by this validation

- Production throughput, load, cost, or availability targets.
- Azure lease-loss injection, network partitions, or cloud poison recovery.
- Unattended recurring execution, or GitHub/Teams event connectors.
- Model selection accuracy beyond the observed examples.
- Translation quality, external-link availability, or general Markdown compatibility.
- Any exactly-once guarantee.

The local retry/poison tests and Azure transport have different retry policies. A production deployment needs reconciliation, alerts, authorization, retention, evaluations, and a deliberate recovery process.

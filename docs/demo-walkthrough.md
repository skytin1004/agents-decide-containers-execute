# Sample documents and the resulting GitHub Issue

This walkthrough takes about three minutes. You can inspect the inputs and a saved result without an Azure subscription. The Issue was created from a verified Azure report. Opening these pages does not run the agent again.

## 1. The request

Imagine asking: **“Check our documentation for broken internal links and translated pages that need review.”**

The approved source is `docs-fixture-v1`, a small snapshot bundled with the worker. The hosted agent can request `check_links`, `check_translation_drift`, both, or no action. Python validates the request before submitting it to Azure Queue Storage.

## 2. The documents

### A link points to a missing file

Open the [English documentation index](../docops/fixture/docs/en/index.md). Its deployment link points to `deploy.md`, which is intentionally absent. The setup link points to an existing file.

```md
Read the [setup guide](setup.md).
Read the [deployment guide](deploy.md).
```

The worker checks the internal link targets within this fixed snapshot. It does not browse external websites.

### The English source has changed

Compare the [English setup guide](../docops/fixture/docs/en/setup.md) with the [Korean setup guide](../docops/fixture/docs/ko/setup.md).

| English source | Korean translation |
| --- | --- |
| Install Python 3.13 and run the documentation checks. | Python 3.13을 설치하고 문서 검사를 실행하세요. |
| The source now includes the queue worker setup. | No corresponding sentence in this example. |

That difference makes the example easy to see. The actual check compares the normalized source hash with the baseline recorded for the translation. A mismatch means **review needed**. The worker does not judge translation quality or use a model to identify missing sentences.

## 3. The resulting Issue

**[Open the Issue on GitHub](https://github.com/skytin1004/agents-decide-containers-execute/issues/1)** · [Offline copy](../samples/issue-demo/issue.md) · [Execution evidence](../samples/issue-demo/README.md)

Request `docops-gh-37010261060` produced Issue #1, **Documentation check: 2 items need attention**, on October 2, 2026.

| Finding | What the maintainer can do |
| --- | --- |
| `docs/en/index.md:6` points to missing `deploy.md` | Fix the link or add the intended document |
| `docs/ko/setup.md` has an older baseline for `docs/en/setup.md` | Review the translated page and update its baseline after review |

The Issue links to the exact source commit and provides review checkboxes. Its **Execution evidence** section is collapsed so that the findings remain the focus. Expand it to inspect the request, report hash and workflow.

The agent selected checks. The worker produced the report. A GitHub Actions publisher validated the committed report and created this Issue. Source files remain unchanged.

## 4. How the responsibilities connect

| Component | Responsibility in this sample |
| --- | --- |
| Microsoft Foundry Routine | Starts an invocation; the sample keeps the schedule disabled and uses manual dispatch |
| Foundry hosted agent | Chooses which approved checks to request |
| Python `submit_checks` tool | Rejects unapproved repository IDs, actions and fields |
| Azure Queue Storage | Carries the validated request |
| Azure Container Apps Job | Runs the deterministic checks in a finite worker execution |
| Azure Blob Storage | Stores the request state and generated report |
| GitHub Actions publisher | Verifies the committed result and creates or reuses an Issue |

The approved source and actions come from the application contract. Running code in a container alone does not establish those boundaries.

## 5. Try it yourself

From the repository root with Python 3.11 or later:

```sh
python -m pip install .
python -m docops.cli demo
```

Open `.artifacts/local/reports/docops-demo-001/report.md`. This local rehearsal uses scripted action selection, SQLite and a real local Python worker. It does not call a model or Azure. See [Azure setup](azure-setup.md) to deploy the hosted agent and cloud worker.

The local command produces a report. Follow [Issue demo setup](issue-demo.md) to run the Azure-to-Issue workflow. It does not monitor GitHub changes, translate documents, edit source or open a pull request.

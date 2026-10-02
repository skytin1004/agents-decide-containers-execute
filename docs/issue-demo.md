# Documentation checks that end in a GitHub Issue

Show the [sample documents](demo-walkthrough.md), then the resulting Issue. The two findings make the outcome visible: a missing internal link and a translation baseline that needs review. The Issue has links to the relevant files at a specific commit and an expandable execution-evidence section.

## What actually runs

1. A maintainer manually starts **Documentation check to Issue** in GitHub Actions.
2. The workflow signs in to Azure with OIDC and dispatches `docops-maintenance`. The Routine invokes the hosted agent.
3. The agent requests approved checks through `submit_checks`. Python validates the fixed repository ID and allowed actions before queue submission.
4. The existing Container Apps Job scales for queued work, checks the bundled snapshot, uploads the report, and commits application completion in Blob Storage.
5. The workflow reads the committed state and report. It checks the request digest, source, selected actions, schema, paths and findings against this fixed fixture. It then creates a GitHub Issue using a deterministic template.

The agent chooses checks; the publisher performs the GitHub write. There is no native Routine-to-Issue connection hidden here. The workflow is the small orchestration layer for this demo. Direct Routine dispatch and the optional viewer stop at the Blob report unless you explicitly run the publisher for that request. The Routine schedule remains disabled; unattended scheduling and event delivery are not demonstrated by this workflow.

## One-time setup

First deploy the sample using [Azure setup](azure-setup.md). Sign in with `az login` and `gh auth login`. Run the configuration script with your existing project and demo Storage account:

```powershell
./scripts/configure-issue-demo.ps1 `
  -SubscriptionId '<subscription-id>' `
  -ResourceGroup '<dedicated-demo-resource-group>' `
  -FoundryProjectResourceId '/subscriptions/<id>/resourceGroups/<group>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>' `
  -FoundryProjectEndpoint 'https://<account>.services.ai.azure.com/api/projects/<project>' `
  -StorageAccount '<demo-storage-account>'
```

The script creates a dedicated `docops-issue-demo` managed identity and a federated credential restricted to this repository’s `main` branch. It grants a custom role for Routine read/dispatch at the existing Foundry project and `Storage Blob Data Reader` at the `docops-results` container. It saves client, tenant, subscription, endpoint and account identifiers as GitHub repository variables. These identifiers are configuration; no Azure secret or personal GitHub token is uploaded. Allow time for Azure role propagation.

The workflow grants `contents: read`, `id-token: write`, and `issues: write`. The agent and worker gain no GitHub permission. The Azure identity cannot modify the reports or queue work directly. Project-scoped Routine permissions cover that project’s Routines; application code selects the fixed `docops-maintenance` name. GitHub’s `issues: write` permission is broader than the publisher’s create-only implementation.

Forks must explicitly change the destination constant, workflow repository guard and OIDC repository configuration before running. The publisher refuses other repositories by default. Main-branch write access is a trust boundary; protect the branch before adapting this for production.

## Run and present

Open **Actions → Documentation check to Issue → Run workflow** on `main`. Choose `both` and leave the request ID empty. The workflow derives a stable `docops-gh-<run-id>` ID. It waits up to eight minutes for application completion; it never treats dispatch acceptance as completion.

Alternatively:

```sh
gh workflow run issue-demo.yml --ref main -f checks=both -f mode=run
```

The successful workflow summary links to the Issue. The workflow artifact includes the raw Azure `report.json`, request state and a publication receipt. Artifacts expire after 30 days; preserve the verified example in the repository for the talk. The source links are pinned to the workflow commit.

Present the documents, open the Issue, and point to its two findings. Expand **Execution evidence** only if someone asks how the result is connected to the execution. A saved Issue is a real previous result, not proof that a new run happened during the talk.

## Retry and recovery

Use GitHub’s **Re-run jobs** for the same workflow run. Its request ID stays the same. A completed request is read without invoking the Routine again; an incomplete request can be resubmitted safely under the worker’s existing duplicate handling. A different action selection with the same ID fails validation.

To publish a request already completed by the viewer or direct Routine dispatch:

```sh
gh workflow run issue-demo.yml --ref main -f checks=both -f mode=publish-existing -f request_id=docops-your-existing-id
```

The publisher scans open and closed Issues directly for a request marker. It verifies the original request and report digests and the bot author before reusing the Issue, preserving maintainer edits and closed state. A failed GET or ambiguous POST fails the workflow. It does not blindly POST again. A retry lists Issues first, which can recover an Issue created before its HTTP response was lost.

Workflow concurrency serializes publishers in this repository. GitHub does not provide a transactional exactly-once Issue-create API; a deleted marker, deleted Issue, external publisher or unusual consistency delay can require manual reconciliation. Multiple matching Issues or conflicting evidence fail closed. The current scan is capped at 10,000 Issues and fails rather than assuming an incomplete scan means no duplicate. Pending workflow runs can be superseded by GitHub concurrency handling; this is a manual demo, not a durable scheduling service.

## Boundaries

Publication completion is distinct from application completion. GitHub permission or network failure can leave a valid Blob report without an Issue. Retry publication using the same request ID.

The fixture comparison rejects unapproved content but is not independent attestation of the container image. The report does not include a Job execution ID or a model reasoning trace. These checks do not translate, edit source files, clone arbitrary repositories, crawl external links, or open a PR. Keep those limits visible when explaining the demo.

See [cleanup](cleanup.md) to remove the dedicated identity, assignments and repository configuration when no longer needed.

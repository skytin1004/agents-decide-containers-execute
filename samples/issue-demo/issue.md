# Documentation check: 2 items need attention

Saved copy of [GitHub Issue #1](https://github.com/skytin1004/agents-decide-containers-execute/issues/1). Created October 2, 2026 at 13:02:43 UTC. Opening this copy does not run Azure.

## Documentation review needed

The Azure worker completed the requested checks. The following items need a maintainer’s review.

### Broken internal link

[docs/en/index.md, line 6](https://github.com/skytin1004/agents-decide-containers-execute/blob/8c4336899f11d306c1b80dfb8f6b95b6065084ed/docops/fixture/docs/en/index.md#L6) points to `deploy.md`, which is missing from the approved snapshot.

- [ ] Fix the link or add the intended document.

### Translation baseline needs review

[docs/ko/setup.md](https://github.com/skytin1004/agents-decide-containers-execute/blob/8c4336899f11d306c1b80dfb8f6b95b6065084ed/docops/fixture/docs/ko/setup.md) needs review against [docs/en/setup.md](https://github.com/skytin1004/agents-decide-containers-execute/blob/8c4336899f11d306c1b80dfb8f6b95b6065084ed/docops/fixture/docs/en/setup.md). The source hash differs from the recorded translation baseline.

This flags a changed source; it does not assess translation quality or generate a translation.

- [ ] Review the translated page and update its baseline after review.

<details>
<summary>Execution evidence</summary>

- Request: `docops-gh-37010261060`
- Approved source: `docs-fixture-v1`
- Checks: `check_links`, `check_translation_drift`
- Application state: **completed** before Issue publication
- Report: `reports/docops-gh-37010261060/report.json` in Azure Blob Storage
- Report SHA-256: `8b26a09ee1b62a705b9d120e26456a77562f73d52476ebbad4bbad0aec215c24`
- [Workflow run and downloadable evidence](https://github.com/skytin1004/agents-decide-containers-execute/actions/runs/37010261060)
- Source links use commit `8c4336899f11d306c1b80dfb8f6b95b6065084ed`

The agent selected the checks. The Container Apps Job ran them and committed the report. A bounded GitHub Actions publisher validated that report and opened this Issue. No source files were edited and no pull request was created.

The request state and report identify application completion. They do not contain a Job execution ID or a model reasoning trace. The publisher verifies agreement with the fixed fixture; it does not independently attest the worker image.

</details>

<!-- docops-request: docops-gh-37010261060 -->
<!-- docops-request-digest: e044c6fea80abe6318dbbfe9348bf6c67b22257b0382086506c8357c00cbf9bb -->
<!-- docops-report-sha256: 8b26a09ee1b62a705b9d120e26456a77562f73d52476ebbad4bbad0aec215c24 -->

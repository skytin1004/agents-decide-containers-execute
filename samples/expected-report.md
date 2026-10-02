# Documentation maintenance report

Request: `docops-demo-001`
Repository: `docs-fixture-v1`
Status: **completed**
Findings: **2**

## check_links

- `docs/en/index.md:6` points to missing `deploy.md`.

## check_translation_drift

- `docs/ko/setup.md` needs review: `docs/en/setup.md` changed since the recorded translation baseline.

The checks inspect a fixed local snapshot. They do not translate, modify files, or open a pull request.

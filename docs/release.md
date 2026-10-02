# Publish the source when ready

Suggested repository name: foundry-routines-container-apps-jobs. The provided ZIP is a source package, not a published repository. No remote GitHub Actions run has occurred.

The package includes application code, fixtures, Bicep, deployment scripts, pinned cloud dependencies, documentation, tests, selected cloud evidence, and an MIT license. It excludes local credentials, private environment files, virtual environments, build outputs, account inventory, and raw response sessions.

After reviewing the extracted package, initialize a repository on the main branch, add the source files, and create a commit. Choose the remote owner and visibility before publishing. Do not upload the working directory's .env or .artifacts directories. No special branch prefix is needed.

Use the README as the repository landing page. After publication, run the included GitHub Actions workflow and confirm the Windows/Linux, Python 3.11/3.13 matrix. Add the verified public URL to the article introduction and presentation sharing message. A local package test is not a substitute for the remote workflow result.

The broader presentation handoff ZIP includes the deck, script, and manuscript. The code ZIP remains focused on the runnable example.

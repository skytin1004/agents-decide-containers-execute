# Published sample

The public repository is [agents-decide-containers-execute](https://github.com/skytin1004/agents-decide-containers-execute). The source ZIP contains the same selected sample files for offline use.

The package includes application code, fixtures, Bicep, deployment scripts, pinned cloud dependencies, documentation, tests, selected cloud evidence, and an MIT license. It excludes local credentials, private environment files, virtual environments, build outputs, account inventory, and raw response sessions.

Start with the [sample walkthrough](demo-walkthrough.md), then open the [recorded Azure report](../samples/azure-report/report.md). The report is an unchanged copy retrieved from Azure Blob Storage. Its provenance file records hashes and retrieval details. Viewing it does not dispatch new cloud work.

The [sample checks workflow](https://github.com/skytin1004/agents-decide-containers-execute/actions/workflows/checks.yml) runs the tests and local demo on Windows and Linux with Python 3.11 and 3.13. Its test environment includes the pinned Foundry projects SDK so the read-only observer test can verify that no Foundry client is created. Consult the workflow for each revision's result. These tests do not deploy Azure resources or validate a fresh cloud execution.

The broader presentation handoff ZIP includes the deck, script, and manuscript. The code ZIP remains focused on the runnable example.

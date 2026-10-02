# Published sample

The public repository is [agents-decide-containers-execute](https://github.com/skytin1004/agents-decide-containers-execute). The source ZIP contains the same selected sample files for offline use.

The package includes application code, fixtures, Bicep, deployment scripts, pinned cloud dependencies, documentation, tests, selected cloud evidence, and an MIT license. It excludes local credentials, private environment files, virtual environments, build outputs, account inventory, and raw response sessions.

Start with the [sample walkthrough](demo-walkthrough.md), then open [Issue #1](https://github.com/skytin1004/agents-decide-containers-execute/issues/1). The Issue was published from an actual Azure result. Its [saved evidence](../samples/issue-demo/README.md) includes the original report bytes, publication receipts, and an offline Issue copy. Viewing it does not dispatch new cloud work. To run the Azure-to-Issue workflow, follow the [Issue setup guide](issue-demo.md).

The [sample checks workflow](https://github.com/skytin1004/agents-decide-containers-execute/actions/workflows/checks.yml) runs the tests and local demo on Windows and Linux with Python 3.11 and 3.13. Its test environment includes the pinned Foundry projects SDK so the read-only observer test can verify that no Foundry client is created. Consult the workflow for each revision's result. These tests do not deploy Azure resources or validate a fresh cloud execution.

The broader presentation handoff ZIP includes the deck, script, and manuscript. The code ZIP remains focused on the runnable example.

# Cleanup

The schedule is disabled by default. A disabled Routine does not delete or stop the hosted agent, ACR, or other billable resources. Keep the demo resources only for as long as needed.

1. Delete the dedicated Routine from the configured project:

~~~powershell
python routines/manage.py delete
~~~

2. In the Foundry project, stop and delete only the dedicated docops-agent and its versions after confirming the name. If you changed FOUNDRY_HOSTED_AGENT_NAME, use that exact name. Preserve the existing Foundry account, project, model deployments, and unrelated agents.

3. Inspect the dedicated resource group before removing it:

~~~powershell
$subscription = '<your-subscription-name-or-id>'
az resource list --subscription $subscription -g rg-docops-oct14 --query '[].{name:name,type:type}' -o table
~~~

4. When the listed contents are exclusively this demo, delete the group. This also deletes stored demo reports:

~~~powershell
az group delete --subscription $subscription -n rg-docops-oct14
~~~

The command asks for confirmation. Do not substitute the existing Foundry project's resource group. Account-scoped demo role assignments disappear with the Storage account and registry. If other scoped assignments were created separately, review and remove only those dedicated assignments.

Local .env and .artifacts may contain environment identifiers or logs. Keep them private, remove them when no longer needed, and never include them in the GitHub package.

## Issue demo additions

Before deleting the demo group, record the object ID of `docops-issue-demo`. Remove only that identity’s role assignment on the existing Foundry project; deleting the demo group does not delete a project-scoped assignment in another group. The Blob assignment is within the demo Storage account. The federated credential is removed with its managed identity.

Remove the custom **DocOps issue demo Routine dispatcher** role only after confirming it has no remaining assignments. Preserve the existing Foundry project, its agents unrelated to this sample, and other identities. Remove the five repository variables added by `configure-issue-demo.ps1` and disable the **Documentation check to Issue** workflow if the deployment is no longer available. Close the demonstration Issue when appropriate; preserving it retains the public example and its provenance.

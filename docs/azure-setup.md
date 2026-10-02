# Azure setup

Provision before presenting. The live demonstration uses existing resources.

## Requirements

- An Azure subscription with permission to deploy resources and assign roles.
- Azure CLI signed in with the intended tenant. PowerShell 7 is recommended for deployment scripts.
- Python 3.11+ locally. The tested hosted runtime is Python 3.13.
- A Microsoft Foundry project with hosted agents and Routines available, plus a deployed chat model supported by the Foundry client. Validation used East US and an existing gpt-4.1-mini deployment.
- Access to invoke the model and manage agents/Routines in that project. Resource Contributor alone does not grant all data-plane access.

The templates create Storage, ACR Basic, a user-assigned identity, Log Analytics, a Container Apps environment, and an event-driven Job. The hosted agent, registry, logs, storage, model use, and executions can incur charges even when a Routine schedule is disabled.

## 1. Install and select the subscription

From the repository root:

~~~powershell
az login
az account list --query "[].{name:name,id:id}" -o table
$subscription = '<your-subscription-name-or-id>'
az account set --subscription $subscription
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -e .
python -m pip install -r requirements-cloud.txt
Copy-Item .env.example .env
~~~

Use your project endpoint, model deployment name, and a dedicated hosted-agent name in .env. Keep the file private. The endpoint has the form https://ACCOUNT.services.ai.azure.com/api/projects/PROJECT. The model value is the deployment name, not an assumed universal model identifier.

Required providers include Microsoft.App, Microsoft.OperationalInsights, Microsoft.Storage, Microsoft.ContainerRegistry, Microsoft.ManagedIdentity, and Microsoft.CognitiveServices. Register missing providers in your subscription before deployment.

## 2. Deploy the worker resources

~~~powershell
./scripts/deploy.ps1 -Subscription $subscription -ResourceGroup rg-docops-oct14 -Location eastus
~~~

This script waits for foundation deployment, builds the worker in ACR, resolves an immutable image digest, and deploys the Job. Docker is not required locally. Outputs are saved privately to .artifacts/deployment.json. Put the returned storage account name in AZURE_STORAGE_ACCOUNT in .env.

Environment creation can take several minutes. If the command remains running, inspect that deployment instead of starting a duplicate:

~~~powershell
az deployment group show --subscription $subscription -g rg-docops-oct14 -n foundation --query properties.provisioningState -o tsv
az containerapp env show --subscription $subscription -g rg-docops-oct14 -n docops-environment --query properties.provisioningState -o tsv
~~~

The worker identity gets Storage Blob Data Contributor, Storage Queue Data Contributor, and AcrPull on the corresponding demo resources. Shared-key Storage access and anonymous Blob access are disabled.

## 3. Deploy and route the hosted agent

~~~powershell
python scripts/hosted_agent.py deploy
python scripts/hosted_agent.py show --version 1
~~~

The deployment command prints its actual version. Use that value rather than assuming 1 for a redeployment. Wait until status is active, then route the endpoint to it:

~~~powershell
python scripts/hosted_agent.py route --version 1
./scripts/grant-agent-storage.ps1 -Subscription $subscription -StorageAccount '<storage-name>' -Version 1
~~~

The role helper reads instance_identity.principal_id from the hosted agent version. This is distinct from the Foundry project's identity. It assigns Blob Contributor and Queue Message Sender at the demo Storage account scope. Allow time for role propagation.

The code archive contains only the agent entrypoint, pinned requirements, the docops module, and fixture files. It excludes .env, local credentials, virtual environments, and private evidence.

## 4. Give the presenter read access to results

For a signed-in human operator:

~~~powershell
$operator = az ad signed-in-user show --query id -o tsv
$storageScope = az storage account show --subscription $subscription -g rg-docops-oct14 -n '<storage-name>' --query id -o tsv
az role assignment create --assignee-object-id $operator --assignee-principal-type User --role 'Storage Blob Data Reader' --scope $storageScope
~~~

A service principal needs its own principal ID and principal type instead. If cloud_status.py returns 403 after assignment, allow propagation and confirm the credential's tenant and principal. Do not work around this with account keys.

## 5. Verify the model and create a disabled Routine

~~~powershell
python scripts/hosted_agent.py invoke --message 'request_id: docops-smoke-001. Hello, how are you?'
python routines/manage.py create
python routines/manage.py show
~~~

The greeting should return no_action without submitting a check. The Routine has a weekday 07:00 UTC schedule but enabled=false. Manual dispatch is deliberate:

~~~powershell
$runId = 'docops-live-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss')
python routines/manage.py dispatch --request-id $runId
python routines/manage.py runs
python scripts/cloud_status.py $runId
~~~

A Finished Routine run is an agent-invocation result. Wait for completed from cloud_status.py to establish worker completion. Verify that actions includes both check_links and check_translation_drift and that the report has the two expected findings. A schema-valid action list can still be semantically incomplete. The recorded successful Azure request is docops-both-001; docops-demo-001 identifies the separate local fixture run.

Do not enable the sample's recurring schedule unchanged: its fixed request ID intentionally deduplicates. A recurring production trigger must supply a distinct ID per logical occurrence and reuse it on retries.

## Compatibility boundary

Routines are GA as of September 24, 2026, while the pinned Python SDK uses project.beta.routines. The hosted adapter remains prerelease. The package versions in requirements-cloud.txt were installed together successfully. Review official documentation and rerun the smoke test before updating them. The local fixture is deliberately narrower than a general GitHub repository maintenance service.

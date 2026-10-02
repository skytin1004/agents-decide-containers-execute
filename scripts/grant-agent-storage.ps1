param(
  [Parameter(Mandatory=$true)][string]$Subscription,
  [string]$ResourceGroup = 'rg-docops-oct14',
  [Parameter(Mandatory=$true)][string]$StorageAccount,
  [Parameter(Mandatory=$true)][string]$Version,
  [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$raw = & $Python (Join-Path $PSScriptRoot 'hosted_agent.py') show --version $Version
if ($LASTEXITCODE -ne 0) { throw 'Cannot read agent identity' }
$agent = $raw | ConvertFrom-Json
$principal = $agent.instance_identity.principal_id
if (-not $principal) { throw 'Agent response has no instance_identity.principal_id' }
$subId = az account show --subscription $Subscription --query id -o tsv
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve subscription' }
$scope = "/subscriptions/$subId/resourceGroups/$ResourceGroup/providers/Microsoft.Storage/storageAccounts/$StorageAccount"
foreach ($role in @('Storage Blob Data Contributor', 'Storage Queue Data Message Sender')) {
  az role assignment create --assignee-object-id $principal --assignee-principal-type ServicePrincipal --role $role --scope $scope --output none
  if ($LASTEXITCODE -ne 0) { throw "Cannot assign $role" }
}
Write-Output 'Agent storage roles assigned at the demo storage account scope.'

param(
  [Parameter(Mandatory=$true)][string]$Subscription,
  [string]$ResourceGroup = 'rg-docops-oct14',
  [string]$Location = 'eastus',
  [string]$ImageTag = '0.1.0'
)
$ErrorActionPreference = 'Stop'
function Assert-Az { if ($LASTEXITCODE -ne 0) { throw 'Azure CLI command failed' } }
$repo = Split-Path -Parent $PSScriptRoot
Push-Location $repo
try {
  az group create --subscription $Subscription -n $ResourceGroup -l $Location --tags purpose=docops-oct14 --output none
  Assert-Az
  $raw = az deployment group create --subscription $Subscription -g $ResourceGroup -n foundation --template-file infra/foundation.bicep --query properties.outputs -o json
  Assert-Az
  $o = $raw | ConvertFrom-Json
  az acr build --subscription $Subscription --registry $o.registryName.value --image "docops-worker:$ImageTag" . --no-logs
  Assert-Az
  $digest = az acr repository show --subscription $Subscription --name $o.registryName.value --image "docops-worker:$ImageTag" --query digest -o tsv
  Assert-Az
  $image = "$($o.registryServer.value)/docops-worker@$digest"
  az deployment group create --subscription $Subscription -g $ResourceGroup -n job --template-file infra/job.bicep --parameters environmentId=$($o.environmentId.value) workerIdentityId=$($o.workerIdentityId.value) workerClientId=$($o.workerClientId.value) storageName=$($o.storageName.value) registryServer=$($o.registryServer.value) image=$image --output none
  Assert-Az
  New-Item -ItemType Directory -Force .artifacts | Out-Null
  @{ subscription=$Subscription; resourceGroup=$ResourceGroup; image=$image; outputs=$o } | ConvertTo-Json -Depth 8 | Set-Content .artifacts/deployment.json -Encoding utf8
  Write-Output "Worker deployed. AZURE_STORAGE_ACCOUNT=$($o.storageName.value)"
  Write-Output 'Next: follow docs/azure-setup.md to deploy the hosted agent and assign its storage roles.'
} finally { Pop-Location }

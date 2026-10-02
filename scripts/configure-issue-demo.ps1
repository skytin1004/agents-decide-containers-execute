# Run once after the Azure sample is deployed. Requires role-assignment rights.
# Repository variables are configuration, not secrets. No GitHub token enters Azure.
param(
    [Parameter(Mandatory)][string]$SubscriptionId,
    [Parameter(Mandatory)][string]$ResourceGroup,
    [Parameter(Mandatory)][string]$FoundryProjectResourceId,
    [Parameter(Mandatory)][string]$FoundryProjectEndpoint,
    [Parameter(Mandatory)][string]$StorageAccount,
    [string]$Repository = "skytin1004/agents-decide-containers-execute"
)
$ErrorActionPreference = "Stop"
function AzJson {
    $result = & az @args --subscription $SubscriptionId --output json
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI failed" }
    if ($result) { return ($result | ConvertFrom-Json) }
}
if ($FoundryProjectResourceId -notmatch "^/subscriptions/$([regex]::Escape($SubscriptionId))/resourceGroups/([^/]+)/providers/Microsoft.CognitiveServices/accounts/[^/]+/projects/[^/]+$") {
    throw "Expected a Foundry project ARM resource in the supplied subscription"
}
$foundryGroup = $Matches[1]
$identity = AzJson identity create --resource-group $ResourceGroup --name docops-issue-demo
$null = AzJson identity federated-credential create --resource-group $ResourceGroup --identity-name docops-issue-demo --name github-main --issuer https://token.actions.githubusercontent.com --subject "repo:${Repository}:ref:refs/heads/main" --audiences api://AzureADTokenExchange
$roleName = "DocOps issue demo Routine dispatcher"
$role = @{
    Name = $roleName
    Description = "Read and dispatch Foundry Routines for the bounded documentation Issue demo"
    IsCustom = $true
    Actions = @("Microsoft.CognitiveServices/accounts/projects/read")
    NotActions = @()
    DataActions = @(
        "Microsoft.CognitiveServices/accounts/AIServices/routines/read",
        "Microsoft.CognitiveServices/accounts/AIServices/routines/dispatch/action"
    )
    NotDataActions = @()
    AssignableScopes = @("/subscriptions/$SubscriptionId/resourceGroups/$foundryGroup")
}
$existing = @(AzJson role definition list --name $roleName)
if ($existing.Count -eq 0) {
    $roleFile = [System.IO.Path]::GetTempFileName()
    try {
        $role | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $roleFile -Encoding utf8
        $null = AzJson role definition create --role-definition $roleFile
    } finally { Remove-Item -LiteralPath $roleFile }
} else {
    $actual = $existing[0]
    if (-not $actual.roleType.Equals("CustomRole") -or
        (($actual.permissions[0].dataActions | Sort-Object) -join ",") -ne (($role.DataActions | Sort-Object) -join ",") -or
        (($actual.permissions[0].actions | Sort-Object) -join ",") -ne (($role.Actions | Sort-Object) -join ",") -or
        ($actual.assignableScopes -join ",") -ne ($role.AssignableScopes -join ",") -or
        @($actual.permissions).Count -ne 1) {
        throw "Existing role differs; inspect it before changing permissions"
    }
}
$null = AzJson role assignment create --assignee-object-id $identity.principalId --assignee-principal-type ServicePrincipal --role $roleName --scope $FoundryProjectResourceId
$storage = AzJson storage account show --resource-group $ResourceGroup --name $StorageAccount
$blobScope = "$($storage.id)/blobServices/default/containers/docops-results"
$null = AzJson role assignment create --assignee-object-id $identity.principalId --assignee-principal-type ServicePrincipal --role "Storage Blob Data Reader" --scope $blobScope
$account = & az account show --subscription $SubscriptionId --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw "Could not read tenant configuration" }
$variables = @{
    AZURE_ISSUE_DEMO_CLIENT_ID = $identity.clientId
    AZURE_TENANT_ID = $account.tenantId
    AZURE_SUBSCRIPTION_ID = $SubscriptionId
    AZURE_STORAGE_ACCOUNT = $StorageAccount
    FOUNDRY_PROJECT_ENDPOINT = $FoundryProjectEndpoint
}
foreach ($entry in $variables.GetEnumerator()) {
    & gh variable set $entry.Key --body $entry.Value --repo $Repository
    if ($LASTEXITCODE -ne 0) { throw "Could not save repository variable $($entry.Key)" }
}
Write-Output "Configured docops-issue-demo: main-branch OIDC, project Routine dispatch, container Blob read, GitHub repository variables."

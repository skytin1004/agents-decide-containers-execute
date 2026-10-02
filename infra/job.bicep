param location string = resourceGroup().location
param environmentId string
param workerIdentityId string
param workerClientId string
param storageName string
param registryServer string
param image string

resource job 'Microsoft.App/jobs@2025-01-01' = {
  name: 'docops-worker'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${workerIdentityId}': {} } }
  properties: {
    environmentId: environmentId
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Event'
      replicaTimeout: 300
      replicaRetryLimit: 0
      registries: [{ server: registryServer, identity: workerIdentityId }]
      eventTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
        scale: {
          minExecutions: 0
          maxExecutions: 2
          pollingInterval: 15
          rules: [{
            name: 'queue-work'
            type: 'azure-queue'
            identity: workerIdentityId
            metadata: {
              accountName: storageName
              queueName: 'docops-work'
              queueLength: '1'
            }
          }]
        }
      }
    }
    template: {
      containers: [{
        name: 'worker'
        image: image
        resources: { cpu: json('0.25'), memory: '0.5Gi' }
        env: [
          { name: 'AZURE_STORAGE_ACCOUNT', value: storageName }
          { name: 'AZURE_CLIENT_ID', value: workerClientId }
          { name: 'DOCOPS_QUEUE', value: 'docops-work' }
          { name: 'DOCOPS_POISON_QUEUE', value: 'docops-poison' }
          { name: 'DOCOPS_CONTAINER', value: 'docops-results' }
        ]
      }]
    }
  }
}
output jobName string = job.name
output jobId string = job.id

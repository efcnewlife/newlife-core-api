using 'main.bicep'

// Proposed name; the operator confirms it is free. postgres, redis, storage, and app-service use the same name.
param location = 'canadacentral'
param tags = {
  app: 'newlife'
  owner: 'newlife-core-api'
  environment: 'staging'
}

param keyVaultName = 'kv-newlife-stg'

param keyVaultSecretsOfficers = [
  { principalId: 'bb173cd3-c29d-4338-8e36-6241bb02284b', principalType: 'User' }
]

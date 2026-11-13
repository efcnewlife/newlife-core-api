using 'main.bicep'

// Proposed name; the operator confirms it is free. Must match app-service/staging.bicepparam.
param location = 'canadacentral'
param tags = {
  app: 'newlife'
  owner: 'newlife-core-api'
  environment: 'staging'
}

param storageAccountName = 'stnewlifecorestg'

param keyVaultName = 'kv-newlife-stg'

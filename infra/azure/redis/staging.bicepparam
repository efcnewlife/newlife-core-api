using 'main.bicep'

// Placement exception: Canada Central had no Balanced B0/B1 capacity on 2026-11-13 (EFC-295, EFC-291).
param location = 'eastus2'
param tags = {
  app: 'newlife'
  owner: 'newlife-core-api'
  environment: 'staging'
}

param redisName = 'redis-newlife-stg'
param redisHighAvailability = 'Disabled'

param keyVaultName = 'kv-newlife-stg'

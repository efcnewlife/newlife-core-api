using 'main.bicep'

// Proposed names; the operator confirms each globally unique name is free before deploying.
// keyVaultName, postgresServerName, postgresDatabaseName, and storageAccountName must match infra/azure/api/staging.bicepparam.
param location = 'canadacentral'
param tags = {
  app: 'newlife'
  owner: 'newlife-core-api'
  environment: 'staging'
}

param postgresServerName = 'psql-newlife-stg'
param redisName = 'redis-newlife-stg'
param storageAccountName = 'stnewlifecorestg'
param keyVaultName = 'kv-newlife-stg'

param postgresAdminLogin = 'newlifeadmin'
param postgresAdminPassword = readEnvironmentVariable('NEWLIFE_PG_ADMIN_PASSWORD')
param postgresDatabaseName = 'newlife-core'

// The operator adds their own public IPv4 address, for example:
//   { name: 'jay-home', ip: '203.0.113.10' }
param postgresOperatorIps = []

param redisHighAvailability = 'Disabled'

// The operator adds their own object ID (az ad signed-in-user show --query id -o tsv), for example:
//   { principalId: '<operator object ID>', principalType: 'User' }
param keyVaultSecretsOfficers = []

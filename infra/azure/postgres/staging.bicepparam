using 'main.bicep'

// Proposed name; the operator confirms it is free. Names must match app-service/staging.bicepparam.
param location = 'canadacentral'
param tags = {
  app: 'newlife'
  owner: 'newlife-core-api'
  environment: 'staging'
}

param postgresServerName = 'psql-newlife-stg'
param postgresAdminLogin = 'newlifeadmin'
param postgresAdminPassword = readEnvironmentVariable('NEWLIFE_PG_ADMIN_PASSWORD')
param postgresDatabaseName = 'newlife-core'

param postgresOperatorIps = [
  { name: 'jay', ip: '173.33.51.225' }
]

param keyVaultName = 'kv-newlife-stg'

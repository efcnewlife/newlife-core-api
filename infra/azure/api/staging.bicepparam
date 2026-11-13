using 'main.bicep'

// Proposed names; the operator confirms each globally unique name is free before deploying.
param environmentName = 'stg'
param location = 'canadaeast'
param tags = {
  app: 'newlife'
  owner: 'newlife-core-api'
  environment: 'staging'
}

param appServicePlanName = 'asp-newlife-api-stg'
param webAppName = 'app-newlife-api-stg'
param postgresServerName = 'psql-newlife-stg'
param redisName = 'redis-newlife-stg'
param storageAccountName = 'stnewlifecorestg'
param keyVaultName = 'kv-newlife-stg'

param appServicePlanSku = 'B1'

// Phase 1: leave NEWLIFE_API_IMAGE_DIGEST unset. Phase 2 and every later infrastructure deployment: set it to
// the digest staging should run (the one already running, unless deploying a new image on purpose).
param apiImageDigest = readEnvironmentVariable('NEWLIFE_API_IMAGE_DIGEST', '')
param appRelease = readEnvironmentVariable('NEWLIFE_API_RELEASE', '')

param registryName = 'efcnewlifecr'
param registryResourceGroup = 'rg-newlife-shared'

param postgresAdminLogin = 'newlifeadmin'
param postgresAdminPassword = readEnvironmentVariable('NEWLIFE_PG_ADMIN_PASSWORD')

// The operator adds their own public IPv4 address, for example:
//   { name: 'jay-home', ip: '203.0.113.10' }
param postgresOperatorIps = []

param redisHighAvailability = 'Disabled'

// The operator adds their own object ID (az ad signed-in-user show --query id -o tsv), for example:
//   { principalId: '<operator object ID>', principalType: 'User' }
param keyVaultSecretsOfficers = []

param dnsZoneName = 'efcnewlife.com'
// Not secrets: the operator fills these in and commits them before phase 2.
param dnsZoneResourceGroup = '<resource group of the efcnewlife.com zone>'
param dnsRecordName = 'api.dev'

param adminPortalUrl = 'https://portal.dev.efcnewlife.com'
param facilityBookingUrl = 'https://booking.dev.efcnewlife.com'
param azureTenantId = ''
param azureAppClientId = ''
param sentryDsn = ''

param mockLoginEnabled = true
param graphMailSendEnabled = false

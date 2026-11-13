using 'main.bicep'

// Proposed names; the operator confirms each globally unique name is free before deploying.
param environmentName = 'stg'
param location = 'canadacentral'
param tags = {
  app: 'newlife'
  owner: 'newlife-core-api'
  environment: 'staging'
}

param appServicePlanName = 'asp-newlife-api-stg'
param webAppName = 'app-newlife-api-stg'
param appServicePlanSku = 'B1'

// Every deployment: the digest staging should run (the one already running, unless deploying a new image on purpose).
param apiImageDigest = readEnvironmentVariable('NEWLIFE_API_IMAGE_DIGEST')
param appRelease = readEnvironmentVariable('NEWLIFE_API_RELEASE')

param registryName = 'efcnewlifecr'
param registryResourceGroup = 'rg-newlife-shared'

// Must match the key-vault, postgres, and storage staging parameters.
param keyVaultName = 'kv-newlife-stg'
param postgresServerName = 'psql-newlife-stg'
param postgresDatabaseName = 'newlife-core'
param storageAccountName = 'stnewlifecorestg'

param apiHostName = 'api.dev.efcnewlife.com'

param adminPortalUrl = 'https://portal.dev.efcnewlife.com'
param facilityBookingUrl = 'https://booking.dev.efcnewlife.com'
// Not secrets: the operator fills these in and commits them before the first app deployment.
param azureTenantId = '1611ced1-d776-4134-acca-a77746e45623'
// Empty until the Admin Portal app registration exists (EFC-297); Microsoft sign-in stays off until then.
param azureAppClientId = ''
param sentryDsn = ''

param mockLoginEnabled = true
param graphMailSendEnabled = false

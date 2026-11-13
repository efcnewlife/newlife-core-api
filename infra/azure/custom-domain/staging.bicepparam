using 'main.bicep'

param webAppName = 'app-newlife-api-stg'
param location = 'canadacentral'

param dnsZoneName = 'efcnewlife.com'
param dnsZoneResourceGroup = 'rg-newlife-shared'
param dnsRecordName = 'api.dev'

param tags = {
  app: 'newlife'
  owner: 'newlife-core-api'
  environment: 'staging'
}

using 'main.bicep'

param webAppName = 'app-newlife-api-stg'
param location = 'canadacentral'

param dnsZoneName = 'efcnewlife.com'
// Not a secret: the operator fills this in and commits it before deploying.
param dnsZoneResourceGroup = '<resource group of the efcnewlife.com zone>'
param dnsRecordName = 'api.dev'

param tags = {
  app: 'newlife'
  owner: 'newlife-core-api'
  environment: 'staging'
}

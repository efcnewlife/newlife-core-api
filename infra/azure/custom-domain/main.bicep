// Custom hostname for an existing Core API Web App: CNAME and domain-verification TXT in the existing public DNS
// zone, a free App Service managed certificate, and an SNI TLS binding. A one-time setup per environment, deployed
// into the Web App's resource group after infra/azure/app-service. Rerun only to change the hostname; App Service
// renews the managed certificate itself. Rerunning rebinds TLS, so HTTPS on the hostname drops briefly.
// Authored and validated offline. A human operator runs what-if and deploys it; see docs/azure-staging-api.md.
targetScope = 'resourceGroup'

@description('Existing Web App from infra/azure/api.')
param webAppName string

@description('Existing public zone; referenced, never created.')
param dnsZoneName string
param dnsZoneResourceGroup string
@description('Record name relative to dnsZoneName, e.g. api.dev for api.dev.efcnewlife.com.')
param dnsRecordName string

@description('Must match the Web App and its Plan.')
param location string = resourceGroup().location

param tags object = {}

var hostName = '${dnsRecordName}.${dnsZoneName}'
var hostSlug = replace(hostName, '.', '-')

resource webApp 'Microsoft.Web/sites@2025-03-01' existing = {
  name: webAppName
}

module dnsRecords 'modules/dns-records.bicep' = {
  name: 'dns-${hostSlug}'
  scope: resourceGroup(dnsZoneResourceGroup)
  params: {
    zoneName: dnsZoneName
    recordName: dnsRecordName
    target: webApp.properties.defaultHostName
    verificationId: webApp.properties.customDomainVerificationId
  }
}

// Bound without TLS first; the managed certificate needs the binding, and hostname-tls then enables SNI.
resource hostNameBinding 'Microsoft.Web/sites/hostNameBindings@2025-03-01' = {
  parent: webApp
  name: hostName
  properties: {
    siteName: webAppName
    hostNameType: 'Verified'
    sslState: 'Disabled'
  }
  dependsOn: [
    dnsRecords
  ]
}

resource certificate 'Microsoft.Web/certificates@2025-03-01' = {
  name: '${webAppName}-${hostSlug}'
  location: location
  tags: tags
  properties: {
    serverFarmId: webApp.properties.serverFarmId
    canonicalName: hostName
  }
  dependsOn: [
    hostNameBinding
  ]
}

module hostNameTls 'modules/hostname-tls.bicep' = {
  name: 'tls-${hostSlug}'
  params: {
    webAppName: webAppName
    hostName: hostName
    thumbprint: certificate.properties.thumbprint
  }
}

output hostName string = hostName
output certificateThumbprint string = certificate.properties.thumbprint

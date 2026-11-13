// CNAME and App Service domain-verification TXT for the API hostname, in the existing public zone.
// The zone is referenced, never created; deployed into the zone's resource group.
targetScope = 'resourceGroup'

param zoneName string

@description('Relative to the zone, e.g. api.dev.')
param recordName string

@description('Web App default hostname, e.g. <app>.azurewebsites.net.')
param target string

param verificationId string

resource zone 'Microsoft.Network/dnsZones@2018-05-01' existing = {
  name: zoneName
}

resource cname 'Microsoft.Network/dnsZones/CNAME@2018-05-01' = {
  parent: zone
  name: recordName
  properties: {
    TTL: 3600
    CNAMERecord: {
      cname: target
    }
  }
}

resource verification 'Microsoft.Network/dnsZones/TXT@2018-05-01' = {
  parent: zone
  name: 'asuid.${recordName}'
  properties: {
    TTL: 3600
    TXTRecords: [
      {
        value: [
          verificationId
        ]
      }
    ]
  }
}

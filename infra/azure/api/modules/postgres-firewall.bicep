// Exact-IP PostgreSQL firewall rules: permanent operator IPs plus every possible outbound IP of the Web App.
// A module so the Web App's runtime outbound IP list can drive the loop. Never the all-Azure-services rule
// (0.0.0.0). Deployments are incremental: removing an IP here does not delete its rule.
targetScope = 'resourceGroup'

param serverName string

param operatorIps operatorIp[]

@description('Comma-separated possibleOutboundIpAddresses of the Web App; empty before the Web App exists.')
param appOutboundIps string

@export()
type operatorIp = {
  @description('Rule suffix: letters, digits, hyphens.')
  name: string
  ip: string
}

var appIps = empty(appOutboundIps) ? [] : split(appOutboundIps, ',')

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2025-08-01' existing = {
  name: serverName
}

// Batched: the server accepts one firewall change at a time.
@batchSize(1)
resource operatorRules 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-08-01' = [
  for entry in operatorIps: {
    parent: server
    name: 'operator-${entry.name}'
    properties: {
      startIpAddress: entry.ip
      endIpAddress: entry.ip
    }
  }
]

@batchSize(1)
resource appRules 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-08-01' = [
  for ip in appIps: {
    parent: server
    name: 'app-outbound-${replace(ip, '.', '-')}'
    properties: {
      startIpAddress: ip
      endIpAddress: ip
    }
    dependsOn: [
      operatorRules
    ]
  }
]

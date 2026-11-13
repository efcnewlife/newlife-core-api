// Exact-IP PostgreSQL firewall rules for every possible outbound IP of the Web App. A module so the Web App's
// runtime outbound IP list can drive the loop. Never the all-Azure-services rule (0.0.0.0). Deployments are
// incremental: an IP the Web App no longer uses keeps its rule until removed by hand.
targetScope = 'resourceGroup'

param serverName string

@description('Comma-separated possibleOutboundIpAddresses of the Web App.')
param appOutboundIps string

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2025-08-01' existing = {
  name: serverName
}

// The server accepts one firewall change at a time.
@batchSize(1)
resource appRules 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-08-01' = [
  for ip in split(appOutboundIps, ','): {
    parent: server
    name: 'app-outbound-${replace(ip, '.', '-')}'
    properties: {
      startIpAddress: ip
      endIpAddress: ip
    }
  }
]

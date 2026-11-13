// Enables SNI TLS on an existing hostname binding once its managed certificate exists. A module because the
// binding is first declared without TLS in main.bicep, and one deployment cannot declare a resource twice.
targetScope = 'resourceGroup'

param webAppName string

param hostName string

param thumbprint string

resource webApp 'Microsoft.Web/sites@2025-03-01' existing = {
  name: webAppName
}

resource binding 'Microsoft.Web/sites/hostNameBindings@2025-03-01' = {
  parent: webApp
  name: hostName
  properties: {
    siteName: webAppName
    hostNameType: 'Verified'
    sslState: 'SniEnabled'
    thumbprint: thumbprint
  }
}

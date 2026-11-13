// Core API App Service for one environment: App Service Plan, Web App for Containers, its role assignments, and the
// PostgreSQL firewall rules for its outbound IPs. Redeployed for every new image. It references the Key Vault,
// PostgreSQL, and Storage from their own templates and never changes them; the custom hostname is infra/azure/custom-domain.
// Public endpoints only: no VNet, Private Endpoints, or Private DNS (removed for cost on 2026-11-10, ADR 0039).
// Authored and validated offline. A human operator runs what-if and deploys it; see docs/azure-staging-api.md.
targetScope = 'resourceGroup'

@description('Application environment, passed to the API as ENV.')
param environmentName 'stg' | 'prod'

param location string = resourceGroup().location

param tags object = {}

// [App Service]
param appServicePlanName string
@description('Globally unique; becomes <name>.azurewebsites.net.')
param webAppName string
@description('Plan size. B1 is the initial candidate; each environment is sized independently.')
param appServicePlanSku string = 'B1'

@description('Image digest (sha256:...) the Web App runs. Redeploying with an older digest rolls the app back.')
param apiImageDigest string

@description('Release identity reported by the API as VERSION: short commit for staging, x.y.z for production (ADR 0038).')
param appRelease string

// [Shared registry]
param registryName string
param registryResourceGroup string

// [Existing resources from infra/azure/key-vault, postgres, and storage]
param keyVaultName string
param postgresServerName string
param postgresDatabaseName string
param storageAccountName string

@description('Public API hostname, passed to the API as APP_FQDN. Bound by infra/azure/custom-domain.')
param apiHostName string

// [Application]
param adminPortalUrl string
param facilityBookingUrl string
param azureTenantId string = ''
param azureAppClientId string = ''
param sentryDsn string = ''
@description('Member mock login for QA (ADR 0014). Always off when environmentName is prod.')
param mockLoginEnabled bool = false
param graphMailSendEnabled bool = false
param graphMailSenderMailbox string = ''
param graphMailOverrideTo string = ''

var blobContainerName = 'files'

// Built-in role ID: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/security
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

// Key Vault secret names. The postgres, redis, and storage templates write the first three; the operator sets the rest before the first app deployment.
var secretNames = {
  databasePassword: 'database-password'
  redisUrl: 'redis-url'
  storageConnectionString: 'storage-connection-string'
  jwtSecretKey: 'jwt-secret-key'
  refreshTokenHashSalt: 'refresh-token-hash-salt'
  refreshTokenHashPepper: 'refresh-token-hash-pepper'
  docsBasicAuthPassword: 'docs-basic-auth-password'
  azureAppClientSecret: 'azure-app-client-secret'
  mockLoginSecret: 'mock-login-secret'
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-11-01' existing = {
  name: registryName
  scope: resourceGroup(registryResourceGroup)
}

resource keyVault 'Microsoft.KeyVault/vaults@2025-05-01' existing = {
  name: keyVaultName
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2025-08-01' existing = {
  name: postgresServerName
}

resource plan 'Microsoft.Web/serverfarms@2025-03-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  kind: 'linux'
  sku: {
    name: appServicePlanSku
    capacity: 1
  }
  properties: {
    reserved: true
  }
}

resource webApp 'Microsoft.Web/sites@2025-03-01' = {
  name: webAppName
  location: location
  tags: tags
  kind: 'app,linux,container'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    clientAffinityEnabled: false
    publicNetworkAccess: 'Enabled'
    keyVaultReferenceIdentity: 'SystemAssigned'
    siteConfig: {
      linuxFxVersion: 'DOCKER|${registry.properties.loginServer}/newlife-core-api@${apiImageDigest}'
      acrUseManagedIdentityCreds: true
      // Keeps the worker and the Pending-payment expiry sweep running; Basic has no deployment slots.
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      appSettings: [
        { name: 'WEBSITES_PORT', value: '8000' }
        { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
        { name: 'ENV', value: environmentName }
        { name: 'VERSION', value: appRelease }
        { name: 'WEB_CONCURRENCY', value: '1' }
        { name: 'APP_FQDN', value: apiHostName }
        { name: 'ADMIN_PORTAL_URL', value: adminPortalUrl }
        { name: 'FACILITY_BOOKING_BASE_URL', value: facilityBookingUrl }
        { name: 'CORS_ALLOWED_ORIGINS', value: '${adminPortalUrl},${facilityBookingUrl}' }
        { name: 'MEMBER_WEB_APPS', value: 'facility-booking|${facilityBookingUrl}' }
        { name: 'DATABASE_HOST', value: postgres.properties.fullyQualifiedDomainName }
        { name: 'DATABASE_PORT', value: '5432' }
        { name: 'DATABASE_USER', value: postgres.properties.administratorLogin }
        { name: 'DATABASE_NAME', value: postgresDatabaseName }
        {
          name: 'DATABASE_PASSWORD'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=${secretNames.databasePassword})'
        }
        { name: 'PGSSLMODE', value: 'verify-full' }
        { name: 'PGSSLROOTCERT', value: '/etc/ssl/certs/ca-certificates.crt' }
        {
          name: 'REDIS_URL'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=${secretNames.redisUrl})'
        }
        {
          name: 'JWT_SECRET_KEY'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=${secretNames.jwtSecretKey})'
        }
        {
          name: 'REFRESH_TOKEN_HASH_SALT'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=${secretNames.refreshTokenHashSalt})'
        }
        {
          name: 'REFRESH_TOKEN_HASH_PEPPER'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=${secretNames.refreshTokenHashPepper})'
        }
        {
          name: 'DOCS_BASIC_AUTH_PASSWORD'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=${secretNames.docsBasicAuthPassword})'
        }
        { name: 'STORAGE_BACKEND', value: 'azure_blob' }
        { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccountName }
        {
          name: 'AZURE_STORAGE_CONNECTION_STRING'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=${secretNames.storageConnectionString})'
        }
        { name: 'AZURE_STORAGE_CONTAINER_NAME', value: blobContainerName }
        { name: 'AZURE_STORAGE_REGION', value: location }
        { name: 'AZURE_TENANT_ID', value: azureTenantId }
        { name: 'AZURE_APP_CLIENT_ID', value: azureAppClientId }
        {
          name: 'AZURE_APP_CLIENT_SECRET'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=${secretNames.azureAppClientSecret})'
        }
        { name: 'SENTRY_DSN', value: sentryDsn }
        { name: 'MOCK_LOGIN_ENABLED', value: mockLoginEnabled && environmentName != 'prod' ? 'true' : 'false' }
        {
          name: 'MOCK_LOGIN_SECRET'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=${secretNames.mockLoginSecret})'
        }
        { name: 'GRAPH_MAIL_SEND_ENABLED', value: graphMailSendEnabled ? 'true' : 'false' }
        { name: 'GRAPH_MAIL_SENDER_MAILBOX', value: graphMailSenderMailbox }
        { name: 'GRAPH_MAIL_OVERRIDE_TO', value: graphMailOverrideTo }
      ]
    }
  }
}

resource webAppLogs 'Microsoft.Web/sites/config@2025-03-01' = {
  parent: webApp
  name: 'logs'
  properties: {
    applicationLogs: {
      fileSystem: {
        level: 'Information'
      }
    }
    httpLogs: {
      fileSystem: {
        enabled: true
        retentionInDays: 7
        retentionInMb: 35
      }
    }
    detailedErrorMessages: {
      enabled: false
    }
    failedRequestsTracing: {
      enabled: false
    }
  }
}

resource ftpPublishing 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2025-03-01' = {
  parent: webApp
  name: 'ftp'
  properties: {
    allow: false
  }
}

resource scmPublishing 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2025-03-01' = {
  parent: webApp
  name: 'scm'
  properties: {
    allow: false
  }
}

resource webAppSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, webApp.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

module webAppAcrPull 'modules/acr-pull.bicep' = {
  name: 'acr-pull-${webAppName}'
  scope: resourceGroup(registryResourceGroup)
  params: {
    registryName: registryName
    principalId: webApp.identity.principalId
  }
}

// The Web App's possible outbound IPs are only known at deployment time, so a module loops over them.
module appOutboundFirewall 'modules/postgres-firewall.bicep' = {
  name: 'postgres-app-outbound-${webAppName}'
  params: {
    serverName: postgres.name
    appOutboundIps: webApp.properties.possibleOutboundIpAddresses
  }
}

output webAppName string = webApp.name
output webAppDefaultHostName string = webApp.properties.defaultHostName
output webAppPrincipalId string = webApp.identity.principalId
output webAppPossibleOutboundIps string = webApp.properties.possibleOutboundIpAddresses

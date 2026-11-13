// Core API environment: App Service Plan + Web App for Containers, PostgreSQL Flexible Server, Azure Managed Redis,
// Blob Storage, and Key Vault. One deployment per environment. The custom hostname and its TLS certificate are a
// one-time setup in infra/azure/api-domain, so redeploying this template never touches them.
// Public endpoints only: no VNet, Private Endpoints, or Private DNS (removed for cost on 2026-11-10, ADR 0039).
// Authored and validated offline. A human operator runs what-if and deploys it; see docs/azure-staging-api.md.
targetScope = 'resourceGroup'

import { operatorIp } from 'modules/postgres-firewall.bicep'

@description('Application environment, passed to the API as ENV.')
param environmentName 'stg' | 'prod'

param location string = resourceGroup().location

param tags object = {}

// [Names]
param appServicePlanName string
@description('Globally unique; becomes <name>.azurewebsites.net.')
param webAppName string
@description('Globally unique; becomes <name>.postgres.database.azure.com.')
param postgresServerName string
param redisName string
@minLength(3)
@maxLength(24)
param storageAccountName string
@minLength(3)
@maxLength(24)
param keyVaultName string

// [App Service]
@description('Plan size. B1 is the initial candidate; each environment is sized independently.')
param appServicePlanSku string = 'B1'

@description('Empty: phase 1, create data services and Key Vault only. Set to the image digest (sha256:...) to create the Plan and Web App.')
param apiImageDigest string = ''

@description('Release identity reported by the API as VERSION: short commit for staging, x.y.z for production (ADR 0038).')
param appRelease string = ''

// [Shared registry]
param registryName string
param registryResourceGroup string

// [PostgreSQL]
param postgresVersion string = '18'
param postgresSkuName string = 'Standard_B1ms'
param postgresSkuTier 'Burstable' | 'GeneralPurpose' | 'MemoryOptimized' = 'Burstable'
param postgresStorageSizeGB int = 32
param postgresAdminLogin string
@secure()
@minLength(16)
@description('Supply on every deployment; it is written to the server and to the database-password secret.')
param postgresAdminPassword string
param postgresDatabaseName string = 'newlife-core'

@description('Permanent developer/operator public IPv4 addresses allowed through the PostgreSQL firewall.')
param postgresOperatorIps operatorIp[] = []

// [Managed Redis]
param redisSkuName string = 'Balanced_B0'
@description('Disabled for staging, Enabled for production.')
param redisHighAvailability 'Enabled' | 'Disabled'

// [Key Vault]
@description('Object IDs that may set and read secrets (Key Vault Secrets Officer), e.g. the operator.')
param keyVaultSecretsOfficers secretsOfficer[] = []

type secretsOfficer = {
  principalId: string
  principalType: 'User' | 'Group' | 'ServicePrincipal'
}

@description('Public API hostname, passed to the API as APP_FQDN. Bound by infra/azure/api-domain.')
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

var deployApi = !empty(apiImageDigest)
var blobContainerName = 'files'

// Built-in role IDs: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/security
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
var keyVaultSecretsOfficerRoleId = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

// Key Vault secret names. The first three are written below from deployment values; the operator sets the rest before phase 2.
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

// [Key Vault]
resource keyVault 'Microsoft.KeyVault/vaults@2025-05-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    // App Service resolves Key Vault references over the public endpoint (no VNet integration).
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

resource secretsOfficerAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for officer in keyVaultSecretsOfficers: {
    name: guid(keyVault.id, officer.principalId, keyVaultSecretsOfficerRoleId)
    scope: keyVault
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsOfficerRoleId)
      principalId: officer.principalId
      principalType: officer.principalType
    }
  }
]

// [PostgreSQL]
resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2025-08-01' = {
  name: postgresServerName
  location: location
  tags: tags
  sku: {
    name: postgresSkuName
    tier: postgresSkuTier
  }
  properties: {
    // Migrations use uuidv7(), which needs PostgreSQL 18.
    version: postgresVersion
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    authConfig: {
      passwordAuth: 'Enabled'
      activeDirectoryAuth: 'Disabled'
    }
    storage: {
      storageSizeGB: postgresStorageSizeGB
      autoGrow: 'Disabled'
    }
    backup: {
      backupRetentionDays: 14
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

resource postgresRequireTls 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2025-08-01' = {
  parent: postgres
  name: 'require_secure_transport'
  properties: {
    value: 'ON'
    source: 'user-override'
  }
}

// Flexible Server rejects concurrent child operations, so its children are applied one after another.
resource postgresDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2025-08-01' = {
  parent: postgres
  name: postgresDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
  dependsOn: [
    postgresRequireTls
  ]
}

module postgresFirewall 'modules/postgres-firewall.bicep' = {
  name: 'postgres-firewall'
  params: {
    serverName: postgres.name
    operatorIps: postgresOperatorIps
    appOutboundIps: deployApi ? webApp!.properties.possibleOutboundIpAddresses : ''
  }
  dependsOn: [
    // The implied path through webApp does not exist in phase 1.
    #disable-next-line no-unnecessary-dependson
    postgresDatabase
  ]
}

resource databasePasswordSecret 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  parent: keyVault
  name: secretNames.databasePassword
  properties: {
    value: postgresAdminPassword
  }
  // Written only after the server accepted the password, so a rejected value never replaces the stored one.
  dependsOn: [
    postgres
  ]
}

// [Managed Redis]
resource redis 'Microsoft.Cache/redisEnterprise@2025-07-01' = {
  name: redisName
  location: location
  tags: tags
  sku: {
    name: redisSkuName
  }
  properties: {
    highAvailability: redisHighAvailability
    minimumTlsVersion: '1.2'
    // Managed Redis has no IP allowlist; access keys and TLS protect the public endpoint.
    publicNetworkAccess: 'Enabled'
  }
}

resource redisDatabase 'Microsoft.Cache/redisEnterprise/databases@2025-07-01' = {
  parent: redis
  name: 'default'
  properties: {
    clientProtocol: 'Encrypted'
    port: 10000
    // The API uses a non-cluster client; never the OSS cluster policy.
    clusteringPolicy: 'NoCluster'
    // When full, evict the least recently used key with a TTL (every key has one) instead of refusing writes.
    // Losing a member refresh binding only forces a new sign-in; refusing writes would fail requests.
    evictionPolicy: 'VolatileLRU'
    // The API has no Entra token support for Redis.
    accessKeysAuthentication: 'Enabled'
  }
}

resource redisUrlSecret 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  parent: keyVault
  name: secretNames.redisUrl
  properties: {
    value: 'rediss://:${uriComponent(redisDatabase.listKeys().primaryKey)}@${redis.properties.hostName}:${redisDatabase.properties.port}/0'
  }
}

// [Blob Storage]
resource storage 'Microsoft.Storage/storageAccounts@2025-08-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    isHnsEnabled: false
    allowBlobPublicAccess: false
    // The Blob adapter signs read SAS URLs with the account key.
    allowSharedKeyAccess: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-08-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 14
    }
  }
}

resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-08-01' = {
  parent: blobService
  name: blobContainerName
  properties: {
    publicAccess: 'None'
  }
}

resource storageConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  parent: keyVault
  name: secretNames.storageConnectionString
  properties: {
    value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
  }
}

// [App Service] phase 2 only: created once an image digest is supplied.
resource plan 'Microsoft.Web/serverfarms@2025-03-01' = if (deployApi) {
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

resource webApp 'Microsoft.Web/sites@2025-03-01' = if (deployApi) {
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
        { name: 'DATABASE_USER', value: postgresAdminLogin }
        { name: 'DATABASE_NAME', value: postgresDatabase.name }
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
        { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storage.name }
        {
          name: 'AZURE_STORAGE_CONNECTION_STRING'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=${secretNames.storageConnectionString})'
        }
        { name: 'AZURE_STORAGE_CONTAINER_NAME', value: blobContainer.name }
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

resource webAppLogs 'Microsoft.Web/sites/config@2025-03-01' = if (deployApi) {
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

resource ftpPublishing 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2025-03-01' = if (deployApi) {
  parent: webApp
  name: 'ftp'
  properties: {
    allow: false
  }
}

resource scmPublishing 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2025-03-01' = if (deployApi) {
  parent: webApp
  name: 'scm'
  properties: {
    allow: false
  }
}

resource webAppSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployApi) {
  name: guid(keyVault.id, webApp.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: webApp!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

module webAppAcrPull 'modules/acr-pull.bicep' = if (deployApi) {
  name: 'acr-pull-${webAppName}'
  scope: resourceGroup(registryResourceGroup)
  params: {
    registryName: registryName
    principalId: webApp!.identity.principalId
  }
}

output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
output postgresFqdn string = postgres.properties.fullyQualifiedDomainName
output redisHostName string = redis.properties.hostName
output storageAccountName string = storage.name
output webAppName string = deployApi ? webApp!.name : ''
output webAppDefaultHostName string = deployApi ? webApp!.properties.defaultHostName : ''
output webAppPrincipalId string = deployApi ? webApp!.identity.principalId : ''
output webAppPossibleOutboundIps string = deployApi ? webApp!.properties.possibleOutboundIpAddresses : ''

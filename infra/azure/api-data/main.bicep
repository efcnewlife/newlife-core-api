// Core API data services for one environment: Key Vault, PostgreSQL Flexible Server, Azure Managed Redis, and Blob
// Storage, plus the secrets derived from them and the operator PostgreSQL firewall rules. Deployed first and rarely;
// the App Service in infra/azure/api references these resources and never changes them.
// Public endpoints only: no VNet, Private Endpoints, or Private DNS (removed for cost on 2026-11-10, ADR 0039).
// Authored and validated offline. A human operator runs what-if and deploys it; see docs/azure-staging-api.md.
targetScope = 'resourceGroup'

param location string = resourceGroup().location

param tags object = {}

// [Names]
@description('Globally unique; becomes <name>.postgres.database.azure.com.')
param postgresServerName string
param redisName string
@minLength(3)
@maxLength(24)
param storageAccountName string
@minLength(3)
@maxLength(24)
param keyVaultName string

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

type operatorIp = {
  @description('Rule suffix: letters, digits, hyphens.')
  name: string
  ip: string
}

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

var blobContainerName = 'files'

// Built-in role ID: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/security
var keyVaultSecretsOfficerRoleId = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

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

// The server accepts one firewall change at a time.
@batchSize(1)
resource operatorRules 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2025-08-01' = [
  for entry in postgresOperatorIps: {
    parent: postgres
    name: 'operator-${entry.name}'
    properties: {
      startIpAddress: entry.ip
      endIpAddress: entry.ip
    }
    dependsOn: [
      postgresDatabase
    ]
  }
]

resource databasePasswordSecret 'Microsoft.KeyVault/vaults/secrets@2025-05-01' = {
  parent: keyVault
  name: 'database-password'
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
  name: 'redis-url'
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
  name: 'storage-connection-string'
  properties: {
    value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
  }
}

output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
output postgresFqdn string = postgres.properties.fullyQualifiedDomainName
output redisHostName string = redis.properties.hostName
output storageAccountName string = storage.name

// PostgreSQL Flexible Server for one environment's Core API: TLS required, exact-IP operator firewall rules, and the
// database-password secret written into the existing Key Vault. Public endpoint only (ADR 0039). The App Service
// template adds the rules for its own outbound IPs.
// Authored and validated offline. A human operator runs what-if and deploys it; see docs/azure-staging-api.md.
targetScope = 'resourceGroup'

param location string = resourceGroup().location

param tags object = {}

@description('Globally unique; becomes <name>.postgres.database.azure.com.')
param postgresServerName string
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

@description('Existing vault from infra/azure/key-vault that receives this template\'s secret.')
param keyVaultName string

resource keyVault 'Microsoft.KeyVault/vaults@2025-05-01' existing = {
  name: keyVaultName
}

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

output postgresFqdn string = postgres.properties.fullyQualifiedDomainName

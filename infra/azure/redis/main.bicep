// Azure Managed Redis for one environment's Core API: TLS, access keys, non-clustered database 0, and the redis-url
// secret written into the existing Key Vault. Managed Redis has no IP allowlist (ADR 0039).
// Authored and validated offline. A human operator runs what-if and deploys it; see docs/azure-staging-api.md.
targetScope = 'resourceGroup'

@description('Staging uses East US 2: Balanced B0 and B1 had no capacity in Canada Central on 2026-11-13 (EFC-295).')
param location string = resourceGroup().location

param tags object = {}

param redisName string
param redisSkuName string = 'Balanced_B0'
@description('Disabled for staging, Enabled for production.')
param redisHighAvailability 'Enabled' | 'Disabled'

@description('Existing vault from infra/azure/key-vault that receives this template\'s secret.')
param keyVaultName string

resource keyVault 'Microsoft.KeyVault/vaults@2025-05-01' existing = {
  name: keyVaultName
}

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

output redisHostName string = redis.properties.hostName

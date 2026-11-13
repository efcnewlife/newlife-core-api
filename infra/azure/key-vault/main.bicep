// Key Vault for one environment's Core API secrets, with Secrets Officer role assignments for operators. Deployed
// first: postgres, redis, and storage write their derived secrets into it, and the App Service reads it.
// Authored and validated offline. A human operator runs what-if and deploys it; see docs/azure-staging-api.md.
targetScope = 'resourceGroup'

param location string = resourceGroup().location

param tags object = {}

@minLength(3)
@maxLength(24)
param keyVaultName string

@description('Object IDs that may set and read secrets (Key Vault Secrets Officer), e.g. the operator.')
param keyVaultSecretsOfficers secretsOfficer[] = []

type secretsOfficer = {
  principalId: string
  principalType: 'User' | 'Group' | 'ServicePrincipal'
}

// Built-in role ID: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/security
var keyVaultSecretsOfficerRoleId = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

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

output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri

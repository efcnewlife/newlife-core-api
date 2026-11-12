// Shared Azure Container Registry (Basic) for Core API images used by staging and production.
// Authored and validated offline. A human operator runs what-if and deploys it; see
// docs/azure-container-registry.md.
targetScope = 'resourceGroup'

@description('Globally unique registry name: 5-50 letters and digits.')
@minLength(5)
@maxLength(50)
param registryName string

param location string = resourceGroup().location

param tags object = {}

@description('Registry-scope role assignments: AcrPull for runtime identities, AcrPush for the publishing operator, AcrDelete for the cleanup operator.')
param roleAssignments roleAssignment[] = []

type roleAssignment = {
  @description('Object ID of the user, group, or service principal (including managed identities).')
  principalId: string
  principalType: 'User' | 'Group' | 'ServicePrincipal'
  role: 'AcrPull' | 'AcrPush' | 'AcrDelete'
}

// Built-in role IDs: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/containers
var roleDefinitionIds = {
  AcrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  AcrPush: '8311e382-0749-4cb8-b61a-304f252e45ec'
  AcrDelete: 'c2f4ef07-c644-48eb-af81-4b1b4947fb11'
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-11-01' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    // AcrPull/AcrPush/AcrDelete are not honored in ABAC repository permissions mode.
    roleAssignmentMode: 'LegacyRegistryPermissions'
    policies: {
      // App Service managed-identity pulls use ARM-audience tokens.
      azureADAuthenticationAsArmPolicy: {
        status: 'enabled'
      }
    }
  }
}

resource registryRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for assignment in roleAssignments: {
    name: guid(registry.id, assignment.principalId, roleDefinitionIds[assignment.role])
    scope: registry
    properties: {
      roleDefinitionId: subscriptionResourceId(
        'Microsoft.Authorization/roleDefinitions',
        roleDefinitionIds[assignment.role]
      )
      principalId: assignment.principalId
      principalType: assignment.principalType
    }
  }
]

output registryId string = registry.id
output registryName string = registry.name
output loginServer string = registry.properties.loginServer

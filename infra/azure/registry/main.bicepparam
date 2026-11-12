using 'main.bicep'

// Proposed name; the operator confirms it is free with `az acr check-name` before deploying.
param registryName = 'efcnewlifecr'

param tags = {
  app: 'newlife'
  owner: 'newlife-core-api'
  environment: 'shared'
}

// The operator adds entries with real object IDs, for example:
//   { principalId: '<operator user object ID>', principalType: 'User', role: 'AcrPush' }
//   { principalId: '<staging Web App identity principal ID>', principalType: 'ServicePrincipal', role: 'AcrPull' }
param roleAssignments = []

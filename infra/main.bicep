targetScope = 'resourceGroup'

@description('Base name for all resources')
param appName string = 'wanderlisted'

@description('Environment name (test or prod)')
@allowed(['test', 'prod'])
param environment string

@description('Azure region')
param location string = resourceGroup().location

@description('Immutable API image digest in sha256:<64 hex> form')
param apiImageDigest string = ''

@description('Immutable frontend image digest in sha256:<64 hex> form')
param frontendImageDigest string = ''

@secure()
@description('PostgreSQL connection string for durable LangGraph checkpoints and the default session registry')
param checkpointDatabaseUrl string = ''

@secure()
@description('Optional separate PostgreSQL connection string for the account session registry')
param sessionRegistryDatabaseUrl string = ''

@secure()
@minLength(32)
@description('At least 32 bytes used to sign anonymous browser-principal cookies')
param sessionSigningKey string

@description('Enable the Atlas Sunrise bilingual workspace')
param chatUiV2Enabled bool = false

@description('Enable Clerk account authentication after every required Clerk value is configured')
param clerkEnabled bool = false

@description('Clerk publishable key; this value is public but environment-specific')
param clerkPublishableKey string = ''

@secure()
@description('Clerk server secret used only by the Next.js server')
param clerkSecretKey string = ''

@description('Expected Clerk token issuer')
param clerkIssuer string = ''

@description('Clerk JWKS endpoint')
param clerkJwksUrl string = ''

@description('Comma-separated HTTPS authorized parties accepted in Clerk tokens')
param clerkAuthorizedParties string = ''

@secure()
@description('Optional dedicated key for deriving opaque account owner identifiers')
param clerkOwnerHashKey string = ''

@secure()
@description('Clerk Svix webhook signing secret')
param clerkWebhookSigningSecret string = ''

@description('Locale-specific consultation URL; an empty value hides the English CTA')
param consultationUrlEn string = ''

@description('Locale-specific consultation URL; an empty value hides the Polish CTA')
param consultationUrlPl string = ''

// ─── Variables ────────────────────────────────────────────────────
var envSuffix = environment == 'prod' ? '' : '-test'
var acrName = replace('${appName}acr', '-', '')
var envName = '${appName}-env${envSuffix}'
var apiAppName = '${appName}-api${envSuffix}'
var frontendAppName = '${appName}-frontend${envSuffix}'
var logAnalyticsName = '${appName}-logs${envSuffix}'
var checkpointConfigured = !empty(checkpointDatabaseUrl)
var registryDatabaseUrl = !empty(sessionRegistryDatabaseUrl) ? sessionRegistryDatabaseUrl : checkpointDatabaseUrl
var registryConfigured = !empty(registryDatabaseUrl)
var frontendOrigin = 'https://${frontendAppName}.${containerEnv.properties.defaultDomain}'

// ─── Log Analytics Workspace ──────────────────────────────────────
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ─── Azure Container Registry ─────────────────────────────────────
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: true }
}

// ─── Container Apps Environment ───────────────────────────────────
resource containerEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ─── Redis Addon ──────────────────────────────────────────────────
resource redis 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appName}-redis${envSuffix}'
  location: location
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: false
        targetPort: 6379
        exposedPort: 6379
        transport: 'tcp'
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      activeRevisionsMode: 'Single'
    }
    template: {
      containers: [
        {
          name: 'redis'
          image: 'redis:7-alpine'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          probes: [
            {
              type: 'Liveness'
              tcpSocket: { port: 6379 }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
            {
              type: 'Readiness'
              tcpSocket: { port: 6379 }
              initialDelaySeconds: 2
              periodSeconds: 5
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

// ─── API Container App ────────────────────────────────────────────
resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: apiAppName
  location: location
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        corsPolicy: {
          allowedOrigins: [frontendOrigin]
          allowedMethods: ['GET', 'POST', 'OPTIONS']
          allowedHeaders: ['Authorization', 'Content-Type', 'X-Request-ID']
        }
      }
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: concat([
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
        {
          name: 'session-signing-key'
          value: sessionSigningKey
        }
      ], checkpointConfigured ? [
        {
          name: 'checkpoint-database-url'
          value: checkpointDatabaseUrl
        }
      ] : [], registryConfigured ? [
        {
          name: 'session-registry-database-url'
          value: registryDatabaseUrl
        }
      ] : [], !empty(clerkOwnerHashKey) ? [
        {
          name: 'clerk-owner-hash-key'
          value: clerkOwnerHashKey
        }
      ] : [], !empty(clerkWebhookSigningSecret) ? [
        {
          name: 'clerk-webhook-signing-secret'
          value: clerkWebhookSigningSecret
        }
      ] : [])
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${acr.properties.loginServer}/${appName}-api@${apiImageDigest}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: concat([
            { name: 'REDIS_URL', value: 'redis://${redis.properties.configuration.ingress.fqdn}:6379' }
            { name: 'RATE_LIMIT_BACKEND', value: 'redis' }
            { name: 'ENVIRONMENT', value: environment }
            { name: 'FRONTEND_URL', value: frontendOrigin }
            { name: 'CHECKPOINT_BACKEND', value: checkpointConfigured ? 'postgres' : 'memory' }
            { name: 'CHECKPOINT_AUTO_SETUP', value: 'true' }
            { name: 'SESSION_SIGNING_KEY', secretRef: 'session-signing-key' }
            { name: 'SESSION_REGISTRY_BACKEND', value: registryConfigured ? 'postgres' : 'memory' }
            { name: 'SESSION_REGISTRY_AUTO_SETUP', value: 'true' }
            { name: 'SESSION_RETENTION_DAYS', value: '365' }
            { name: 'CLERK_ENABLED', value: string(clerkEnabled) }
            { name: 'CLERK_ISSUER', value: clerkIssuer }
            { name: 'CLERK_JWKS_URL', value: clerkJwksUrl }
            { name: 'CLERK_AUTHORIZED_PARTIES', value: clerkAuthorizedParties }
          ], checkpointConfigured ? [
            { name: 'CHECKPOINT_DATABASE_URL', secretRef: 'checkpoint-database-url' }
          ] : [], registryConfigured ? [
            { name: 'SESSION_REGISTRY_DATABASE_URL', secretRef: 'session-registry-database-url' }
          ] : [], !empty(clerkOwnerHashKey) ? [
            { name: 'CLERK_OWNER_HASH_KEY', secretRef: 'clerk-owner-hash-key' }
          ] : [], !empty(clerkWebhookSigningSecret) ? [
            { name: 'CLERK_WEBHOOK_SIGNING_SECRET', secretRef: 'clerk-webhook-signing-secret' }
          ] : [])
        }
      ]
      scale: {
        minReplicas: environment == 'prod' ? 1 : 0
        maxReplicas: environment == 'prod' ? 3 : 2
        rules: [
          {
            name: 'http-scaling'
            http: { metadata: { concurrentRequests: '20' } }
          }
        ]
      }
    }
  }
}

// ─── Frontend Container App ───────────────────────────────────────
resource frontendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: frontendAppName
  location: location
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 3000
        transport: 'http'
      }
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: acr.properties.loginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: concat([
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
      ], !empty(clerkSecretKey) ? [
        {
          name: 'clerk-secret-key'
          value: clerkSecretKey
        }
      ] : [])
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: '${acr.properties.loginServer}/${appName}-frontend@${frontendImageDigest}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: concat([
            { name: 'API_URL', value: 'https://${apiApp.properties.configuration.ingress.fqdn}' }
            { name: 'CHAT_UI_V2_ENABLED', value: string(chatUiV2Enabled) }
            { name: 'CLERK_ENABLED', value: string(clerkEnabled) }
            { name: 'CLERK_PUBLISHABLE_KEY', value: clerkPublishableKey }
            { name: 'CONSULTATION_URL_EN', value: consultationUrlEn }
            { name: 'CONSULTATION_URL_PL', value: consultationUrlPl }
          ], !empty(clerkSecretKey) ? [
            { name: 'CLERK_SECRET_KEY', secretRef: 'clerk-secret-key' }
          ] : [])
        }
      ]
      scale: {
        minReplicas: environment == 'prod' ? 1 : 0
        maxReplicas: environment == 'prod' ? 2 : 1
        rules: [
          {
            name: 'http-scaling'
            http: { metadata: { concurrentRequests: '30' } }
          }
        ]
      }
    }
  }
}

// ─── Outputs ──────────────────────────────────────────────────────
output acrLoginServer string = acr.properties.loginServer
output apiUrl string = 'https://${apiApp.properties.configuration.ingress.fqdn}'
output frontendUrl string = 'https://${frontendApp.properties.configuration.ingress.fqdn}'
output environmentName string = containerEnv.name

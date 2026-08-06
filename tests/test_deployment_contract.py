"""Static release contracts that must hold before any Azure mutation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_production_promotes_existing_sha_images_without_rebuilding():
    workflow = _read(".github/workflows/deploy-prod.yml")

    assert "image_sha:" in workflow
    assert "^[0-9a-f]{40}$" in workflow
    assert "wanderlisted-api:${{ steps.image.outputs.sha }}" in workflow
    assert "wanderlisted-frontend:${{ steps.image.outputs.sha }}" in workflow
    assert "apiImageDigest=${{ steps.digests.outputs.api_digest }}" in workflow
    assert (
        "frontendImageDigest=${{ steps.digests.outputs.frontend_digest }}" in workflow
    )
    assert "docker build" not in workflow
    assert "az acr import" not in workflow


def test_test_workflow_builds_commit_sha_once_and_exports_both_digests():
    workflow = _read(".github/workflows/deploy-test.yml")

    assert "IMAGE_TAG: ${{ github.sha }}" in workflow
    assert "org.opencontainers.image.revision=${{ env.IMAGE_TAG }}" in workflow
    assert "api_digest: ${{ steps.digests.outputs.api_digest }}" in workflow
    assert "frontend_digest: ${{ steps.digests.outputs.frontend_digest }}" in workflow
    assert "--build-arg API_URL" not in workflow


def test_bicep_pins_both_container_images_by_digest():
    template = _read("infra/main.bicep")

    assert "${appName}-api@${apiImageDigest}" in template
    assert "${appName}-frontend@${frontendImageDigest}" in template
    assert "${appName}-api:${imageTag}" not in template
    assert "${appName}-frontend:${imageTag}" not in template


def test_frontend_api_target_is_runtime_configuration():
    dockerfile = _read("frontend/Dockerfile")
    next_config = _read("frontend/next.config.ts")
    route_handler = _read("frontend/src/app/api/v1/[...path]/route.ts")

    assert "ARG API_URL" not in dockerfile
    assert "async rewrites" not in next_config
    assert "process.env.API_URL" in route_handler
    assert 'export const dynamic = "force-dynamic"' in route_handler


def test_atlas_workspace_is_canonical_and_clerk_rollout_is_disabled_by_default():
    template = _read("infra/main.bicep")
    test_parameters = _read("infra/parameters.test.bicepparam")
    prod_parameters = _read("infra/parameters.prod.bicepparam")

    assert "param clerkEnabled bool = false" in template
    assert "CHAT_UI_V2_ENABLED" not in template
    assert "{ name: 'CLERK_ENABLED', value: string(clerkEnabled) }" in template
    assert "CONSULTATION_URL_EN" in template
    assert "CONSULTATION_URL_PL" in template
    assert "CLERK_SECRET_KEY', secretRef: 'clerk-secret-key" in template
    assert "param clerkEnabled = false" in test_parameters
    assert "param clerkEnabled = false" in prod_parameters


def test_session_registry_uses_postgres_and_keeps_clerk_secrets_in_secret_refs():
    template = _read("infra/main.bicep")

    assert "param sessionRegistryDatabaseUrl string = ''" in template
    assert "SESSION_REGISTRY_BACKEND" in template
    assert "SESSION_REGISTRY_DATABASE_URL', secretRef:" in template
    assert "CLERK_OWNER_HASH_KEY', secretRef:" in template
    assert "CLERK_WEBHOOK_SIGNING_SECRET', secretRef:" in template


def test_deployment_injects_session_key_and_uses_internal_shared_redis():
    template = _read("infra/main.bicep")
    test_workflow = _read(".github/workflows/deploy-test.yml")
    prod_workflow = _read(".github/workflows/deploy-prod.yml")
    compose = _read("docker-compose.yml")

    assert "param sessionSigningKey string" in template
    assert "SESSION_SIGNING_KEY" in template
    assert "sessionSigningKey='${{ secrets.SESSION_SIGNING_KEY }}'" in test_workflow
    assert "sessionSigningKey='${{ secrets.SESSION_SIGNING_KEY }}'" in prod_workflow
    assert "transport: 'tcp'" in template
    assert "external: false" in template
    assert "redis.properties.configuration.ingress.fqdn" in template
    assert "{ name: 'RATE_LIMIT_BACKEND', value: 'redis' }" in template
    assert "condition: service_healthy" in compose
    assert "redis-cli" in compose


def test_platform_cors_matches_frontend_and_api_can_scale_horizontally():
    template = _read("infra/main.bicep")

    assert "allowedOrigins: [frontendOrigin]" in template
    assert "allowedOrigins: ['*']" not in template
    assert "allowedHeaders: ['*']" not in template
    assert "{ name: 'FRONTEND_URL', value: frontendOrigin }" in template
    assert "maxReplicas: environment == 'prod' ? 3 : 2" in template

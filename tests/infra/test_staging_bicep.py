"""
Offline policy checks for the staging Core API Bicep (EFC-295).

Compiles each per-resource template under infra/azure (key-vault, postgres, redis, storage, app-service,
custom-domain) with the local Bicep CLI and checks the decisions they must encode: no private networking, Always On
container on port 8000, exact-IP PostgreSQL rules, staging Redis without HA in its East US 2 placement exception,
private Blob with soft delete, secrets as Key Vault references, the shared registry referenced rather than created,
each template creating only its own resource, and names agreeing across the parameter files.
Never signs in to Azure; a passing run does not prove Azure accepts the templates.

    uv run pytest tests/infra/test_staging_bicep.py -v
"""

import ipaddress
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterator

import pytest

AZURE_DIR = Path(__file__).resolve().parents[2] / "infra" / "azure"

# Resource types each template owns; no other template may create them.
OWNED_TYPES = {
    "key-vault": ["Microsoft.KeyVault/vaults"],
    "postgres": ["Microsoft.DBforPostgreSQL/flexibleServers"],
    "redis": ["Microsoft.Cache/redisEnterprise"],
    "storage": ["Microsoft.Storage/storageAccounts"],
    "app-service": ["Microsoft.Web/serverfarms", "Microsoft.Web/sites"],
    "custom-domain": [
        "Microsoft.Network/dnsZones/CNAME",
        "Microsoft.Network/dnsZones/TXT",
        "Microsoft.Web/sites/hostNameBindings",
        "Microsoft.Web/certificates",
    ],
}
FOLDERS = list(OWNED_TYPES)


def _bicep() -> str | None:
    configured = os.getenv("BICEP")
    if configured:
        return shutil.which(configured)
    fallback = Path.home() / ".azure" / "bin" / "bicep"
    return shutil.which("bicep") or (str(fallback) if fallback.exists() else None)


BICEP = _bicep()
pytestmark = pytest.mark.skipif(BICEP is None, reason="bicep not found; install it with: az bicep install")


def _compile(command: str, path: Path) -> dict[str, Any]:
    env = {
        **os.environ,
        "NEWLIFE_PG_ADMIN_PASSWORD": "offline-validation-placeholder",
        "NEWLIFE_API_IMAGE_DIGEST": "sha256:offline-validation-placeholder",
        "NEWLIFE_API_RELEASE": "offline",
    }
    result = subprocess.run([BICEP, command, str(path), "--stdout"], capture_output=True, text=True, check=True, env=env)
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def templates() -> dict[str, dict[str, Any]]:
    return {folder: _compile("build", AZURE_DIR / folder / "main.bicep") for folder in FOLDERS}


@pytest.fixture(scope="module")
def staging() -> dict[str, dict[str, Any]]:
    params = {}
    for folder in FOLDERS:
        compiled = json.loads(_compile("build-params", AZURE_DIR / folder / "staging.bicepparam")["parametersJson"])
        params[folder] = {name: entry.get("value") for name, entry in compiled["parameters"].items()}
    return params


def _resources(template: dict[str, Any]) -> Iterator[dict[str, Any]]:
    resources = template.get("resources", [])
    for resource in resources.values() if isinstance(resources, dict) else resources:
        yield resource
        if resource["type"] == "Microsoft.Resources/deployments":
            yield from _resources(resource["properties"]["template"])


def _created(template: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    return [r for r in _resources(template) if r["type"].lower() == resource_type.lower() and not r.get("existing")]


def _one(template: dict[str, Any], resource_type: str) -> dict[str, Any]:
    matches = _created(template, resource_type)
    assert len(matches) == 1, f"expected one {resource_type}, found {len(matches)}"
    return matches[0]


def _app_settings(template: dict[str, Any]) -> dict[str, str]:
    site_config = _one(template, "Microsoft.Web/sites")["properties"]["siteConfig"]
    return {setting["name"]: setting["value"] for setting in site_config["appSettings"]}


def _secret_names(template: dict[str, Any]) -> list[str]:
    return [r["name"] for r in _created(template, "Microsoft.KeyVault/vaults/secrets")]


def test_staging_parameters_agree_across_templates(staging):
    app = staging["app-service"]
    assert app["environmentName"] == "stg"
    assert app["apiHostName"] == "api.dev.efcnewlife.com"
    domain = staging["custom-domain"]
    assert f"{domain['dnsRecordName']}.{domain['dnsZoneName']}" == app["apiHostName"]
    assert domain["webAppName"] == app["webAppName"]
    for folder in ["postgres", "redis", "storage", "app-service"]:
        assert staging[folder]["keyVaultName"] == staging["key-vault"]["keyVaultName"], folder
    for name in ["postgresServerName", "postgresDatabaseName"]:
        assert app[name] == staging["postgres"][name], name
    assert app["storageAccountName"] == staging["storage"]["storageAccountName"]


def test_regional_resources_are_in_canada_central_except_redis_in_east_us_2(staging):
    locations = {folder: staging[folder]["location"] for folder in FOLDERS}
    assert locations == {**dict.fromkeys(FOLDERS, "canadacentral"), "redis": "eastus2"}


def test_each_template_creates_only_its_own_resources(templates):
    for folder, template in templates.items():
        foreign = [t for other, types in OWNED_TYPES.items() if other != folder for t in types]
        assert {t: _created(template, t) for t in foreign} == dict.fromkeys(foreign, []), folder
        assert all(_created(template, t) for t in OWNED_TYPES[folder]), folder


def test_data_templates_write_their_secrets_into_the_existing_vault(templates):
    expected = {"postgres": "database-password", "redis": "redis-url", "storage": "storage-connection-string"}
    for folder, secret in expected.items():
        names = _secret_names(templates[folder])
        assert len(names) == 1 and secret in names[0], (folder, names)


def test_no_private_endpoints_vnets_or_nat_are_created(templates):
    forbidden = {
        "microsoft.network/privateendpoints",
        "microsoft.network/privatednszones",
        "microsoft.network/virtualnetworks",
        "microsoft.network/natgateways",
        "microsoft.network/virtualnetworkgateways",
    }
    for folder, template in templates.items():
        assert not [r["type"] for r in _resources(template) if r["type"].lower() in forbidden], folder
    assert "virtualNetworkSubnetId" not in _one(templates["app-service"], "Microsoft.Web/sites")["properties"]


def test_web_app_runs_the_registry_image_by_digest_with_always_on_on_port_8000(templates):
    site = _one(templates["app-service"], "Microsoft.Web/sites")
    site_config = site["properties"]["siteConfig"]
    assert site["properties"]["httpsOnly"] is True
    assert site["identity"]["type"] == "SystemAssigned"
    assert site_config["alwaysOn"] is True
    assert site_config["acrUseManagedIdentityCreds"] is True
    assert site_config["ftpsState"] == "Disabled"
    assert "/newlife-core-api@" in site_config["linuxFxVersion"]
    assert _app_settings(templates["app-service"])["WEBSITES_PORT"] == "8000"


def test_secret_app_settings_are_key_vault_references(templates):
    settings = _app_settings(templates["app-service"])
    secrets = [
        "DATABASE_PASSWORD",
        "REDIS_URL",
        "JWT_SECRET_KEY",
        "REFRESH_TOKEN_HASH_SALT",
        "REFRESH_TOKEN_HASH_PEPPER",
        "AZURE_STORAGE_CONNECTION_STRING",
        "AZURE_APP_CLIENT_SECRET",
        "DOCS_BASIC_AUTH_PASSWORD",
        "MOCK_LOGIN_SECRET",
    ]
    assert {name: "@Microsoft.KeyVault(" in settings.get(name, "") for name in secrets} == dict.fromkeys(secrets, True)


def test_postgres_requires_tls_and_allows_only_exact_ips(templates, staging):
    server = _one(templates["postgres"], "Microsoft.DBforPostgreSQL/flexibleServers")["properties"]
    assert server["network"]["publicNetworkAccess"] == "Enabled"
    assert server["highAvailability"]["mode"] == "Disabled"
    assert server["backup"] == {"backupRetentionDays": 14, "geoRedundantBackup": "Disabled"}
    tls = [c for c in _created(templates["postgres"], "Microsoft.DBforPostgreSQL/flexibleServers/configurations") if "require_secure_transport" in c["name"]]
    assert [c["properties"]["value"] for c in tls] == ["ON"]

    for folder in ["postgres", "app-service"]:
        rules = _created(templates[folder], "Microsoft.DBforPostgreSQL/flexibleServers/firewallRules")
        assert rules and all(r["properties"]["startIpAddress"] == r["properties"]["endIpAddress"] for r in rules), folder
    for entry in staging["postgres"]["postgresOperatorIps"]:
        address = ipaddress.IPv4Address(entry["ip"])
        assert not (address.is_unspecified or address.is_private), entry


def test_staging_redis_is_tls_access_key_non_clustered_without_ha(templates, staging):
    cluster = _one(templates["redis"], "Microsoft.Cache/redisEnterprise")
    database = _one(templates["redis"], "Microsoft.Cache/redisEnterprise/databases")["properties"]
    assert staging["redis"]["redisHighAvailability"] == "Disabled"
    assert cluster["properties"]["minimumTlsVersion"] == "1.2"
    assert database["clientProtocol"] == "Encrypted"
    assert database["accessKeysAuthentication"] == "Enabled"
    assert database["clusteringPolicy"] == "NoCluster"
    assert database["evictionPolicy"] == "VolatileLRU"


def test_blob_storage_is_private_hot_lrs_with_14_day_soft_delete(templates):
    storage = templates["storage"]
    account = _one(storage, "Microsoft.Storage/storageAccounts")
    assert account["sku"]["name"] == "Standard_LRS"
    assert account["properties"]["allowBlobPublicAccess"] is False
    assert account["properties"]["isHnsEnabled"] is False
    assert account["properties"]["accessTier"] == "Hot"
    service = _one(storage, "Microsoft.Storage/storageAccounts/blobServices")["properties"]
    assert service["deleteRetentionPolicy"] == {"enabled": True, "days": 14}
    assert service["containerDeleteRetentionPolicy"] == {"enabled": True, "days": 14}
    assert _one(storage, "Microsoft.Storage/storageAccounts/blobServices/containers")["properties"]["publicAccess"] == "None"


def test_shared_registry_is_referenced_not_created(templates):
    assert not _created(templates["app-service"], "Microsoft.ContainerRegistry/registries")


def test_custom_domain_binds_the_existing_web_app_in_the_existing_zone(templates):
    domain = templates["custom-domain"]
    assert not _created(domain, "Microsoft.Network/dnsZones")
    binding_states = [b["properties"]["sslState"] for b in _created(domain, "Microsoft.Web/sites/hostNameBindings")]
    assert sorted(binding_states) == ["Disabled", "SniEnabled"]

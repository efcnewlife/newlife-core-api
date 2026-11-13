"""
Offline policy checks for the staging Core API Bicep (EFC-295).

Compiles infra/azure/api and infra/azure/api-domain with the local Bicep CLI and checks the decisions the templates
must encode: no private networking, Always On container on port 8000, exact-IP PostgreSQL rules, staging Redis
without HA, private Blob with soft delete, secrets as Key Vault references, the shared registry referenced rather
than created, and the one-time hostname/TLS setup kept out of the frequently redeployed API template.
Never signs in to Azure; a passing run does not prove Azure accepts the template.

    uv run pytest tests/infra/test_api_bicep.py -v
"""

import ipaddress
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterator

import pytest

ROOT = Path(__file__).resolve().parents[2]
API_DIR = ROOT / "infra" / "azure" / "api"
DOMAIN_DIR = ROOT / "infra" / "azure" / "api-domain"


def _bicep() -> str | None:
    configured = os.getenv("BICEP")
    if configured:
        return shutil.which(configured)
    fallback = Path.home() / ".azure" / "bin" / "bicep"
    return shutil.which("bicep") or (str(fallback) if fallback.exists() else None)


BICEP = _bicep()
pytestmark = pytest.mark.skipif(BICEP is None, reason="bicep not found; install it with: az bicep install")


def _compile(command: str, path: Path) -> dict[str, Any]:
    env = {**os.environ, "NEWLIFE_PG_ADMIN_PASSWORD": "offline-validation-placeholder"}
    result = subprocess.run([BICEP, command, str(path), "--stdout"], capture_output=True, text=True, check=True, env=env)
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def template() -> dict[str, Any]:
    return _compile("build", API_DIR / "main.bicep")


def _parameters(path: Path) -> dict[str, Any]:
    params = _compile("build-params", path)
    return {name: entry.get("value") for name, entry in json.loads(params["parametersJson"])["parameters"].items()}


@pytest.fixture(scope="module")
def staging() -> dict[str, Any]:
    return _parameters(API_DIR / "staging.bicepparam")


@pytest.fixture(scope="module")
def domain_template() -> dict[str, Any]:
    return _compile("build", DOMAIN_DIR / "main.bicep")


@pytest.fixture(scope="module")
def domain_staging() -> dict[str, Any]:
    return _parameters(DOMAIN_DIR / "staging.bicepparam")


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


def test_staging_parameters_target_the_staging_hostname_in_canada_central(staging, domain_staging):
    assert staging["environmentName"] == "stg"
    assert staging["location"] == "canadacentral"
    assert staging["apiHostName"] == "api.dev.efcnewlife.com"
    assert f"{domain_staging['dnsRecordName']}.{domain_staging['dnsZoneName']}" == staging["apiHostName"]
    assert domain_staging["webAppName"] == staging["webAppName"]
    assert domain_staging["location"] == staging["location"]


def test_no_private_endpoints_vnets_or_nat_are_created(template):
    forbidden = {
        "microsoft.network/privateendpoints",
        "microsoft.network/privatednszones",
        "microsoft.network/virtualnetworks",
        "microsoft.network/natgateways",
        "microsoft.network/virtualnetworkgateways",
    }
    assert not [r["type"] for r in _resources(template) if r["type"].lower() in forbidden]
    assert "virtualNetworkSubnetId" not in _one(template, "Microsoft.Web/sites")["properties"]


def test_web_app_runs_the_registry_image_by_digest_with_always_on_on_port_8000(template):
    site = _one(template, "Microsoft.Web/sites")
    site_config = site["properties"]["siteConfig"]
    assert site["properties"]["httpsOnly"] is True
    assert site["identity"]["type"] == "SystemAssigned"
    assert site_config["alwaysOn"] is True
    assert site_config["acrUseManagedIdentityCreds"] is True
    assert site_config["ftpsState"] == "Disabled"
    assert "/newlife-core-api@" in site_config["linuxFxVersion"]
    assert _app_settings(template)["WEBSITES_PORT"] == "8000"


def test_secret_app_settings_are_key_vault_references(template):
    settings = _app_settings(template)
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


def test_postgres_requires_tls_and_allows_only_exact_ips(template, staging):
    server = _one(template, "Microsoft.DBforPostgreSQL/flexibleServers")["properties"]
    assert server["network"]["publicNetworkAccess"] == "Enabled"
    assert server["highAvailability"]["mode"] == "Disabled"
    assert server["backup"] == {"backupRetentionDays": 14, "geoRedundantBackup": "Disabled"}
    tls = [c for c in _created(template, "Microsoft.DBforPostgreSQL/flexibleServers/configurations") if "require_secure_transport" in c["name"]]
    assert [c["properties"]["value"] for c in tls] == ["ON"]

    rules = _created(template, "Microsoft.DBforPostgreSQL/flexibleServers/firewallRules")
    assert rules and all(r["properties"]["startIpAddress"] == r["properties"]["endIpAddress"] for r in rules)
    for entry in staging["postgresOperatorIps"]:
        address = ipaddress.IPv4Address(entry["ip"])
        assert not (address.is_unspecified or address.is_private), entry


def test_staging_redis_is_tls_access_key_non_clustered_without_ha(template, staging):
    cluster = _one(template, "Microsoft.Cache/redisEnterprise")
    database = _one(template, "Microsoft.Cache/redisEnterprise/databases")["properties"]
    assert staging["redisHighAvailability"] == "Disabled"
    assert cluster["properties"]["minimumTlsVersion"] == "1.2"
    assert database["clientProtocol"] == "Encrypted"
    assert database["accessKeysAuthentication"] == "Enabled"
    assert database["clusteringPolicy"] == "NoCluster"
    assert database["evictionPolicy"] == "NoEviction"


def test_blob_storage_is_private_hot_lrs_with_14_day_soft_delete(template):
    account = _one(template, "Microsoft.Storage/storageAccounts")
    assert account["sku"]["name"] == "Standard_LRS"
    assert account["properties"]["allowBlobPublicAccess"] is False
    assert account["properties"]["isHnsEnabled"] is False
    assert account["properties"]["accessTier"] == "Hot"
    service = _one(template, "Microsoft.Storage/storageAccounts/blobServices")["properties"]
    assert service["deleteRetentionPolicy"] == {"enabled": True, "days": 14}
    assert service["containerDeleteRetentionPolicy"] == {"enabled": True, "days": 14}
    assert _one(template, "Microsoft.Storage/storageAccounts/blobServices/containers")["properties"]["publicAccess"] == "None"


def test_shared_registry_is_referenced_not_created(template):
    assert not _created(template, "Microsoft.ContainerRegistry/registries")


def test_api_template_leaves_hostname_dns_and_tls_to_the_domain_template(template):
    domain_types = ["Microsoft.Network/dnsZones/CNAME", "Microsoft.Network/dnsZones/TXT", "Microsoft.Web/sites/hostNameBindings", "Microsoft.Web/certificates"]
    assert {t: _created(template, t) for t in domain_types} == dict.fromkeys(domain_types, [])


def test_domain_template_binds_the_existing_web_app_in_the_existing_zone(domain_template):
    assert not _created(domain_template, "Microsoft.Web/sites")
    assert not _created(domain_template, "Microsoft.Network/dnsZones")
    assert _created(domain_template, "Microsoft.Network/dnsZones/CNAME")
    assert _created(domain_template, "Microsoft.Network/dnsZones/TXT")
    assert _created(domain_template, "Microsoft.Web/certificates")
    binding_states = [b["properties"]["sslState"] for b in _created(domain_template, "Microsoft.Web/sites/hostNameBindings")]
    assert sorted(binding_states) == ["Disabled", "SniEnabled"]

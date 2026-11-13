# Shared container registry and image publication

Runbook for [EFC-294](https://linear.app/jayhsia/issue/EFC-294) under the [Azure deployment plan](azure-deployment.md) and [ADR 0039](adr/0039-azure-deployment-and-release-direction.md). Builds on the [Core API image runbook](azure-core-api-image.md).

Execution boundary: agents author Bicep, scripts, docs, and offline/local checks only. Every Azure account or registry operation below marked **(human)** is performed by a human operator. No agent or CI job signs in to Azure, pushes or pulls through ACR, grants roles, or deletes images.

| Verification | Who | Status |
| --- | --- | --- |
| `scripts/validate-bicep.sh` (compile, lint, format; warnings fail) | Agent | Passed 2026-11-12, Bicep CLI 0.49.2 |
| Local `linux/amd64` image build with OCI labels + `scripts/local-image-smoke.sh` | Agent | Passed 2026-11-12, see [Local build record](#local-build-record) |
| Registry deployment, role assignments, push, pull, lock, cleanup | Human operator | **Pending** — see [Human verification checklist](#human-verification-checklist) |
| Canada East registry deleted, name free again | Human operator | Done 2026-11-12 (operator-reported: `az acr check-name` returned `true`; deletion time not given) |
| Registry recreated in Canada Central, roles re-granted, image republished | Human operator | **Pending** — see [Move the registry to Canada Central](#move-the-registry-to-canada-central-human) |

Offline Bicep validation does not prove that Azure accepts the template. Only the operator's `what-if` and deployment do.

## What the template creates

`infra/azure/registry/main.bicep` (resource group scope) with parameters in `main.bicepparam`:

- One **Basic** registry, shared by staging and production. Proposed name `efcnewlifecr` (login server `efcnewlifecr.azurecr.io`); the operator confirms the name is free.
- Region **Canada Central** (`canadacentral`), pinned by `location` in `main.bicepparam` so the registry does not follow the resource group's region. The earlier Canada East choice is superseded ([ADR 0039](adr/0039-azure-deployment-and-release-direction.md), 2026-11-12).
- **Admin user disabled.** No admin password, repository token, or service principal secret is used anywhere.
- **Classic RBAC mode** (`roleAssignmentMode: LegacyRegistryPermissions`). AcrPull/AcrPush/AcrDelete are not honored in ABAC repository mode, so the mode is pinned instead of left to a future default.
- **ARM-audience Entra tokens enabled** (`azureADAuthenticationAsArmPolicy`). App Service managed-identity pulls fail with `UNAUTHORIZED` without it.
- **Public endpoint, authenticated only.** Basic has no private endpoints, network rules, or anonymous pull.
- Optional **registry-scope role assignments**, each limited to `AcrPull`, `AcrPush`, or `AcrDelete`.
- Outputs `registryId`, `registryName`, `loginServer`. No credentials are output.

Not available on Basic, so not assumed: retention policy for untagged manifests (Premium preview only), geo-replication, private endpoints, content trust. Included storage is 10 GiB.

## Identities and permissions

| Who | Identity | Role at registry scope | When |
| --- | --- | --- | --- |
| Operator (publish, lock, cleanup) | Their own Entra user | `Reader` + `AcrPush` (includes pull), plus `AcrDelete` | `AcrDelete` only for a cleanup session |
| Staging Web App | System-assigned managed identity | `AcrPull` | After the Web App exists ([EFC-295](https://linear.app/jayhsia/issue/EFC-295)) |
| Production Web App | System-assigned managed identity | `AcrPull` | After the Web App exists |
| GitHub Actions | **None** | None | — |

- `Reader` (control plane) covers `az acr show-usage`, `az acr show`, and `az webapp config show`. Data-plane roles (`AcrPull`/`AcrPush`/`AcrDelete`) do not.
- Deploying the template needs `Contributor` on the resource group. Creating its role assignments also needs `Role Based Access Control Administrator` (or `Owner`) there. These are the deploying human's own permissions, not template outputs.
- Removing an entry from `roleAssignments` does **not** revoke it; deployments are incremental. Revoke by hand, for example after a cleanup session:
  `az role assignment delete --assignee <object ID> --role AcrDelete --scope <registryId output>`
- Web Apps set `acrUseManagedIdentityCreds: true` and get only `AcrPull`. They never get push or delete.
- **CI has no Azure identity.** Main/tag CI may build and test the image and keep it as a CI artifact outside Azure. It never pushes to ACR. A future CI publisher (a GitHub OIDC federated credential with `AcrPush` only, bound to a protected environment with a required reviewer and manual dispatch) is a design option only. It contradicts ADR 0039 today and needs a new decision before anyone creates it.

## Deploy the registry (human)

```bash
az login
az account set --subscription "<grant subscription>"
az group show --name rg-newlife-shared --query location -o tsv     # if it exists, skip the next line
az group create --name rg-newlife-shared --location canadacentral
az acr check-name --name efcnewlifecr                               # expect "nameAvailable": true

# Optional: grant roles in the same deployment. Get object IDs without pasting secrets:
az ad signed-in-user show --query id -o tsv
# Edit roleAssignments in infra/azure/registry/main.bicepparam, then:
scripts/validate-bicep.sh

az deployment group what-if --resource-group rg-newlife-shared \
  --template-file infra/azure/registry/main.bicep --parameters infra/azure/registry/main.bicepparam
# Review: one Basic registry in canadacentral, adminUserEnabled false, only the role assignments you expect.
az deployment group create --resource-group rg-newlife-shared --name newlife-registry \
  --template-file infra/azure/registry/main.bicep --parameters infra/azure/registry/main.bicepparam
az deployment group show --resource-group rg-newlife-shared --name newlife-registry --query properties.outputs
```

To add the Web App `AcrPull` assignments later, add entries to `roleAssignments` and repeat `what-if` and `create`. Existing assignments are kept because their names are derived from registry, principal, and role.

## Move the registry to Canada Central (human)

The operator first created `efcnewlifecr` in Canada East. A registry cannot change region, so it is deleted and recreated under the same name. Deleting a registry also deletes its images and the role assignments on it.

1. Delete the Canada East registry. Nothing runs from it yet.

   ```bash
   az acr show --name efcnewlifecr --query "{name:name, location:location, rg:resourceGroup}" -o table
   az acr delete --name efcnewlifecr --resource-group rg-newlife-shared --yes
   ```

2. Wait until the name is free. This can take a few minutes; repeat until it prints `true`.

   ```bash
   az acr check-name --name efcnewlifecr --query nameAvailable
   ```

3. Check the resource group's region. A resource group's region is metadata only: it says where the group's own records live, not where its resources run. The registry's region comes from `location` in `main.bicepparam`, which is `canadacentral`.

   ```bash
   az group show --name rg-newlife-shared --query location -o tsv
   az resource list --resource-group rg-newlife-shared -o table
   ```

   - `canadacentral`: keep it.
   - `canadaeast` and the list is empty: delete it and create it again in Canada Central, so it matches everything else.

     ```bash
     az group delete --name rg-newlife-shared --yes
     az group create --name rg-newlife-shared --location canadacentral
     ```

   - `canadaeast` and it still holds other resources: keep it. Do not delete those resources for this. Record the group's region on the ticket.

4. Recreate the registry with [Deploy the registry](#deploy-the-registry-human). Skip `az group create` there: the group already exists, and creating it again in another region fails. In `what-if`, check that the registry's `location` is `canadacentral`. Then check the live region:

   ```bash
   az acr show --name efcnewlifecr --query location -o tsv   # expect canadacentral
   ```

5. Grant the roles again. The old assignments were deleted with the old registry, and listing them in `roleAssignments` again recreates them. Grant the operator `Reader` the same way it was granted before.

6. Publish the image again with [Publish, verify, and lock](#publish-verify-and-lock-human) and post a new image record. Mark every earlier Canada East image record as superseded in a reply on its ticket, for example `Superseded 2026-11-12: registry recreated in Canada Central; this digest no longer exists.` Never deploy a digest from a superseded record.

## Image names and tags

- Repository: `newlife-core-api`.
- Release images: tag `x.y.z`, the same as the Git tag (no `v`).
- Main candidates: tag `main-<first 12 characters of the commit>`.
- Never `latest` or any tag that moves. Every pushed tag and digest is locked against overwrite.
- Deployments select the **digest** (`efcnewlifecr.azurecr.io/newlife-core-api@sha256:…`). The tag is for people; the digest is what runs.
- Each image carries OCI labels, so a digest always leads back to its source:

  | Label | Value |
  | --- | --- |
  | `org.opencontainers.image.source` | `https://github.com/efcnewlife/newlife-core-api` |
  | `org.opencontainers.image.revision` | full commit SHA |
  | `org.opencontainers.image.version` | the tag |
  | `org.opencontainers.image.created` | commit time (`git show -s --format=%cI HEAD`) |

## Build and test locally (agent or human)

Build for `linux/amd64`. App Service runs amd64, and Apple Silicon builds arm64 unless told otherwise. `--provenance=false --sbom=false` keeps the pushed artifact a single image manifest instead of an index with attestation entries, which App Service support is untested for.

Release images are built on the operator's machine from the exact Git tag, because CI has no registry access. A CI-built image artifact is later work ([EFC-296](https://linear.app/jayhsia/issue/EFC-296)).

```bash
git status --porcelain                      # must print nothing: build only committed source
REV=$(git rev-parse HEAD)
TAG="main-${REV:0:12}"                      # or, on a release tag: TAG=$(git describe --exact-match --tags)
docker build --platform linux/amd64 --provenance=false --sbom=false \
  --label org.opencontainers.image.source=https://github.com/efcnewlife/newlife-core-api \
  --label org.opencontainers.image.revision="$REV" \
  --label org.opencontainers.image.version="$TAG" \
  --label org.opencontainers.image.created="$(git show -s --format=%cI HEAD)" \
  -t "newlife-core-api:$TAG" .
SMOKE_SKIP_BUILD=1 scripts/local-image-smoke.sh "newlife-core-api:$TAG"
```

Only an image that passed the smoke test is published. The smoke never contacts Azure.

### Local build record

2026-11-12, agent, Docker 29.7.2 on arm64 with amd64 emulation, built from a clean detached worktree with the command above:

```text
Source: efcnewlife/newlife-core-api @ 6c002f1814973421a7732cb4f5f400251bde516a (main)   Tag: main-6c002f181497
Local image ID: sha256:6e3f306b7283581e6254f80f3b65e9e568fcdf31ed66ebe31d798bb05e1408fe
Platform: linux/amd64   Compressed size: about 296 MB (docker save | gzip)
Labels: source, revision, version, created as above   Smoke: SMOKE PASSED (all steps)
```

One of three amd64-emulated smoke runs that day failed only the last step (`lifespan shutdown did not finish` after `docker stop -t 30`); the other two passed it. The failing run's container logs were not kept, so the cause (slow emulated shutdown or a real shutdown race) is unknown. If it recurs, rerun with `SMOKE_KEEP=1` and read `docker logs newlife-smoke-api`.

The local image ID is not the registry digest. The digest exists only after the human pushes.

## Publish, verify, and lock (human)

```bash
REG=efcnewlifecr
LOGIN=$REG.azurecr.io
az acr login --name "$REG"                  # Entra token; no admin password

# 1. The tag must not exist yet. Expect an error saying the image is not found.
az acr repository show --name "$REG" --image "newlife-core-api:$TAG"

# 2. Push.
docker tag "newlife-core-api:$TAG" "$LOGIN/newlife-core-api:$TAG"
docker push "$LOGIN/newlife-core-api:$TAG"
DIGEST=$(az acr repository show --name "$REG" --image "newlife-core-api:$TAG" --query digest -o tsv)

# 3. Lock the tag and the digest: no overwrite, no delete.
az acr repository update --name "$REG" --image "newlife-core-api:$TAG" --write-enabled false
az acr repository update --name "$REG" --image "newlife-core-api@$DIGEST" --write-enabled false

# 4. Pull by digest from a clean cache and check the labels.
docker image rm "$LOGIN/newlife-core-api:$TAG" "newlife-core-api:$TAG"
docker pull "$LOGIN/newlife-core-api@$DIGEST"
docker image inspect -f '{{.Architecture}} {{index .Config.Labels "org.opencontainers.image.revision"}}' "$LOGIN/newlife-core-api@$DIGEST"
# Expect: amd64 <the same $REV>

docker logout "$LOGIN"
```

Then post the image record as a comment on the release or deployment ticket. Linear already links the PR and commit, so the record adds what only exists after the push: the tag, digest, and lock state.

```text
Image record   Operator: <name>   UTC: <time>
Source: efcnewlife/newlife-core-api @ <full commit SHA>   Git tag: <x.y.z | none (main)>
Image: efcnewlifecr.azurecr.io/newlife-core-api:<tag>
Digest: sha256:<…>   Platform: linux/amd64
Local smoke: passed   Pull by digest: pass   Revision label matches: yes
Locked: tag + digest (write disabled)
Deployed: none | staging <UTC> | production <UTC>
```

Rollback chooses an earlier record's digest. Never rebuild an old commit to get a rollback image.

## Cleanup (human)

Basic has no retention policy, so cleanup is manual. It is only needed when storage approaches the 10 GiB included in Basic.

Never delete:

1. Any release tag `x.y.z`.
2. The digest running in staging and the digest running in production.
3. The previous deployed digest in each environment (rollback target).
4. The 5 newest `main-*` candidates.

```bash
REG=efcnewlifecr
az acr show-usage --name "$REG" -o table                                    # storage used
az acr manifest list-metadata --registry "$REG" --name newlife-core-api \
  --orderby time_desc -o table                                               # digests, tags, times
# Running digests (after EFC-295):
az webapp config show --resource-group <rg> --name <app> --query linuxFxVersion -o tsv
```

Write down the digests to delete and check each one against the keep list above and the image records. Deleting a digest also deletes every tag on it, so skip any digest that carries a release tag `x.y.z`, even if it also has a `main-*` tag. For each candidate:

```bash
az acr repository update --name "$REG" --image "newlife-core-api@<digest>" --write-enabled true
az acr repository update --name "$REG" --image "newlife-core-api:<tag>" --write-enabled true
az acr repository delete --name "$REG" --image "newlife-core-api@<digest>" --yes
```

A locked digest cannot be deleted, so a candidate that was not deliberately unlocked stays. Record what was deleted on the ticket.

## Human verification checklist

All items are pending until the operator posts evidence (command output with no keys or tokens) on EFC-294. Evidence from the deleted Canada East registry does not count; repeat each item against the Canada Central registry.

- [ ] `az acr show --name efcnewlifecr --query location` prints `canadacentral`.
- [ ] The resource group's region and how it was handled (kept, or recreated in `canadacentral`) are recorded.
- [ ] Earlier Canada East image records are marked superseded.
- [ ] `what-if` shows one Basic registry with `adminUserEnabled: false`, `roleAssignmentMode: LegacyRegistryPermissions`, `azureADAuthenticationAsArmPolicy: enabled`, and only the expected role assignments.
- [ ] Deployment succeeds; outputs show `loginServer`.
- [ ] `az acr credential show --name efcnewlifecr` fails because the admin user is disabled.
- [ ] Operator with `AcrPush` can `az acr login`, push, and pull. A user without a role gets `unauthorized`.
- [ ] Locking (`az acr repository update --write-enabled false`) succeeds for an operator with `Reader` + `AcrPush` only. If it is refused, record the role that was needed.
- [ ] `az acr manifest show-metadata` for the pushed tag shows a single image manifest media type, not an index.
- [ ] Pushing to an existing locked tag fails.
- [ ] Deleting a locked digest fails; after unlocking a throwaway test image, deleting it succeeds.
- [ ] Pull by digest returns `amd64` and the expected revision label.
- [ ] Image record posted for the first published image.
- [ ] `az acr show-usage` reported after the first push (compare with the 10 GiB included storage).
- [ ] Later, with EFC-295: Web App managed identity with `AcrPull` pulls the image by digest; if App Service rejects digest references, record that and use the locked tag instead.

# Core API image publication

Runbook for [EFC-294](https://linear.app/jayhsia/issue/EFC-294) under the [Azure deployment plan](azure-deployment.md) and [ADR 0039](adr/0039-azure-deployment-and-release-direction.md). Builds on the [Core API image runbook](azure-core-api-image.md). Run these steps from a `newlife-core-api` checkout.

The shared registry itself (template, region, role assignments, its verification checklist) is infrastructure and lives in `newlife-infra`: see the [shared container registry runbook](https://github.com/efcnewlife/newlife-infra/blob/main/docs/azure-container-registry.md). Deploy the registry and grant your `AcrPush` role there first.

Execution boundary: agents author scripts, docs, and offline/local checks only. Every Azure account or registry operation below marked **(human)** is performed by a human operator. No agent signs in to Azure, pushes or pulls through ACR, or deletes images. Since [EFC-322](https://linear.app/jayhsia/issue/EFC-322) (ADR 0039), the one exception is the CI workflow: once the operator has set up its OIDC identity, it publishes `main` and release-tag images and deploys them to staging ([CI publication](#ci-publication)).

| Verification | Who | Status |
| --- | --- | --- |
| Local `linux/amd64` image build with OCI labels + `scripts/local-image-smoke.sh` | Agent | Passed 2026-11-12, see [Local build record](#local-build-record) |
| Push, pull, lock, cleanup | Human operator | **Pending** — see the registry runbook's [human verification checklist](https://github.com/efcnewlife/newlife-infra/blob/main/docs/azure-container-registry.md#human-verification-checklist) |
| `scripts/acr-publish.sh`, `scripts/release-target.sh`, `scripts/deploy-staging.sh` against fake `az`/`docker`/`curl` (`scripts/*.test.sh`) | Agent | Passed 2026-11-13 |
| CI publication and staging deployment with OIDC | Human operator | **Pending** — set up and verified with the [staging release runbook](https://github.com/efcnewlife/newlife-infra/blob/main/docs/azure-staging-release.md) |

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

CI builds and publishes `main` and release-tag images ([CI publication](#ci-publication)). Build by hand only when CI publication is off or broken.

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

## CI publication

`.github/workflows/ci.yml` ([EFC-311](https://linear.app/jayhsia/issue/EFC-311)):

| Event | Tests, image build, local smoke | Publish to ACR | Deploy staging |
| --- | --- | --- | --- |
| Pull request, `release/*` branch | Yes | No | No |
| Push to `main` | Yes | Tag `main-<12-char commit>` | Yes |
| Tag `x.y.z` on a commit of an `origin/release/*` branch | Yes | Tag `x.y.z` | Yes |
| Any other tag (`v1.0.0`, `1.0`, `1.0.0-rc.1`, a tag only on `main`) | Fails in `release-target.sh` | No | No |

- `scripts/release-target.sh` decides the image tag. The staging `VERSION` (Sentry release, ADR 0038) is the 7-character commit, for tags too.
- `scripts/acr-publish.sh` pushes the smoke-tested image, then locks the tag and the digest. It never overwrites a tag: an existing tag with the same revision label is reused (a rerun), any other existing tag fails the run. A refused lock fails the run before deployment.
- `scripts/deploy-staging.sh` changes only the staging Web App's image digest and `VERSION`, then waits for `/healthz`. A failed smoke fails the run and prints the previous image. It never rolls back.
- Staging deployments run one at a time (`concurrency: staging-api-deploy`). A running one is never cancelled. GitHub keeps only the newest waiting run, so an image whose deployment was superseded stays published and can be deployed by hand.
- Each deployment keeps `release-record.json` (commit, tag, digest, previous image, smoke result) as a 90-day run artifact and in the run summary. The image tag and the `org.opencontainers.image.revision` label keep the mapping after that.
- The workflow never migrates a database, reads its revision, or changes a firewall. The operator migrates staging after the deployment and deploys production by hand ([staging release runbook](https://github.com/efcnewlife/newlife-infra/blob/main/docs/azure-staging-release.md)).
- Publication stays off until the repository variable `AZURE_CLIENT_ID` is set; until then `main` and tag runs stop after the smoke test with a notice.

## Publish, verify, and lock (human)

Fallback when CI publication is off or broken.

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
# Running digests (after EFC-310 creates the staging Web App):
az webapp config show --resource-group <rg> --name <app> --query linuxFxVersion -o tsv
```

Write down the digests to delete and check each one against the keep list above and the image records. Deleting a digest also deletes every tag on it, so skip any digest that carries a release tag `x.y.z`, even if it also has a `main-*` tag. For each candidate:

```bash
az acr repository update --name "$REG" --image "newlife-core-api@<digest>" --write-enabled true
az acr repository update --name "$REG" --image "newlife-core-api:<tag>" --write-enabled true
az acr repository delete --name "$REG" --image "newlife-core-api@<digest>" --yes
```

A locked digest cannot be deleted, so a candidate that was not deliberately unlocked stays. Record what was deleted on the ticket.

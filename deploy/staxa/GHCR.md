# Manual GHCR publication

`.github/workflows/staxa-ghcr.yml` publishes only on `workflow_dispatch`.
It builds `deploy/staxa/Dockerfile` with repository-root context, including
unchanged shared security overrides and custom addons. No runtime credentials,
secrets or token build arguments are passed. Registry login happens after build,
using only `GITHUB_TOKEN`, with job-scoped `packages: write` and `contents: read`.
Credentials are stored outside the build context and removed even on failure.
The sole image tag is `sha-<full selected commit SHA>`; no `latest` tag is emitted.
Image source/revision labels link it to this repository. The successful run summary
reports the exact image reference only after push and registry-manifest verification.

## Activation blocker

The new workflow is only in PR #21. GitHub requires a new dispatch workflow to be
present on the default branch before it can be invoked. No merge or publication
was performed. Do not work around this by publishing on push or changing main.
After a separately authorized merge, select Actions → Publish Staxa image to GHCR
(manual) → Run workflow, choosing the reviewed branch/commit. No PAT is required.
Package visibility/pull access must be verified separately before any hosting use;
publishing does not automatically grant an external host access to a private image.
Publication is not a deployment or approval of Staxa storage/access readiness.

Reference: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow

## Validation, 2026-11-14

- actionlint v1.7.12: PASS (shellcheck integration disabled; Bash execution tested below).
  Its initial validation caught an invalid job-level `runner.temp` context; moved
  registry configuration to step-level env and revalidated successfully.
- Five workflow tests: PASS (manual-only permissions, successful command ordering,
  build failure prevents login/push, push/manifest failures suppress success output,
  credential cleanup). Docker is mocked: these are orchestration tests, not publication.
- Existing 14 deployment tests and runtime-generation parity: PASS locally.
- Dockerfile, dockerignore, addons and security runtime unchanged. Actual image build
  and custom-module/login proof remain at focused CI run 43615820586, tested commit
  a74d9206cbc77fe1e3eb8f0b184ced0f70246344. No new Docker build was run locally:
  Docker is unavailable. New OCI label flags and GHCR push remain untested in Actions.
- No 207-test rerun. This commit uses `[skip ci]` to avoid the existing broad PR suite;
  it does not prevent a future authorized workflow_dispatch run.
- Publication: BLOCKED / NOT RUN. No published image address is claimed.

Repeat local checks with Python + PyYAML installed:

```sh
python3 deploy/staxa/generate_dockerfile.py --check
python3 deploy/staxa/test_deployment.py
python3 deploy/staxa/test_ghcr_workflow.py
actionlint -shellcheck= .github/workflows/staxa-ghcr.yml
```

# Alpha release policy

This repository is prepared as a single-mainline alpha project.

## Branch policy

- `main` is the only long-lived branch.
- Feature, fix, and release work should be merged back into `main` and deleted after merge.
- Do not keep separate deployment, staging, or release branches for alpha builds.

## Alpha version

The current alpha is tracked in [`VERSION`](../VERSION). Keep the FastAPI app version and release notes aligned with this value.

## Automated alpha pipeline

Every push to `main` runs the alpha pipeline:

1. Install Python dependencies.
2. Run the backend test suite.
3. Build the Docker image.
4. Publish `ghcr.io/waseem7/beat-analyzer:alpha`, `:<VERSION>`, `:sha-<shortsha>`, and `:build-<github-run-number>` when the tests pass.

Pull requests targeting `main` run the same tests and Docker build without publishing an image.

## Deployment expectation

Users should not need to manually commit, pull, or build for normal alpha publishing. The deployable Docker image is produced automatically from `main` after CI succeeds. Synology deployments should use immutable version tags such as `ghcr.io/waseem7/beat-analyzer:0.1.0-alpha.2` instead of relying only on the moving `alpha` tag.

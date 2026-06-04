# Download a fresh project ZIP from GitHub

Binary ZIP files are not stored directly in this repository. Instead, GitHub Actions builds a fresh ZIP artifact from the current commit so the repository stays source-only.

## Manual download steps

1. Open the repository on GitHub.
2. Select the **Actions** tab.
3. Open the **Project ZIP Artifact** workflow.
4. Select **Run workflow**.
5. Keep the branch set to `main` unless you intentionally want another branch.
6. Select **Run workflow** again in the dialog.
7. Wait for the workflow run to finish.
8. Open the completed workflow run.
9. In the **Artifacts** section, download the artifact named like `Beat-Analyzer-latest-<commit>.zip`.

The downloaded ZIP contains the repository source under a `Beat-Analyzer/` folder, including deployment files such as `Dockerfile`, `docker-compose.yml`, and `.github/workflows/alpha.yml`.

# Project journal

A short log of decisions, problems, and fixes. Newest entries at the bottom.

## 2026-11-16 - Phase 0: bootstrap

- Chose the project: Neches Network Health, a synthetic fiber-telemetry lakehouse on Databricks and AWS.
- Created the public repo (MIT licence). Enabled GitHub secret protection and push protection.
- Configured pre-commit with gitleaks (local binary) plus standard hygiene hooks.
- Verified that gitleaks blocks a fake AWS key (rule aws-access-token) before it can be committed.
- Problem: WSL failed to start with "Access is denied" on the Ubuntu disk file. Starting it once from an elevated PowerShell fixed it, and the normal window worked afterwards. Root cause is still open.

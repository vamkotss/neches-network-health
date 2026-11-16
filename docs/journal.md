# Project journal

A short log of decisions, problems, and fixes. Newest entries at the bottom.

## 2026-11-16 - Phase 0: bootstrap

- Chose the project: Neches Network Health, a synthetic fiber-telemetry lakehouse on Databricks and AWS.
- Created the public repo (MIT licence). Enabled GitHub secret protection and push protection.
- Configured pre-commit with gitleaks (local binary) plus standard hygiene hooks.
- Verified that gitleaks blocks a fake AWS key (rule aws-access-token) before it can be committed.
- Problem: WSL failed to start with "Access is denied" on the Ubuntu disk file. Starting it once from an elevated PowerShell fixed it, and the normal window worked afterwards. Root cause is still open.

## 2026-11-16 - Phase 0 complete, Phase 1 started

- Phase 0 finished: repo, secret scanning, pre-commit, Python skeleton, CI green.
- Downloads from PyPI timed out because IPv6 does not work inside WSL. IPv4 works, and a longer uv timeout got past it.
- Push over HTTPS failed because GitHub rejects passwords. Switching the remote to SSH fixed it.
- Phase 1: wrote the domain primer and the data design.

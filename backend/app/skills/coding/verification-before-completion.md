---
name: verification-before-completion
purpose: Only deterministic checks can prove completion
task_types: verification
source: https://github.com/obra/superpowers
attribution: Adapted from obra/superpowers
version: 2026-01
---
A code-changing task is complete only when the project's own deterministic checks pass: tests, typecheck, lint, build — as configured in the project profile. Saying 'done' is never sufficient. If verification fails, read the failure, fix the root cause, and verify again. Never claim completion with failing or skipped checks.

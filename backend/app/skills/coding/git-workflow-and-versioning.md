---
name: git-workflow-and-versioning
purpose: Use git as recovery infrastructure with atomic commits
task_types: git, verification
source: https://github.com/obra/superpowers
attribution: Adapted from obra/superpowers
version: 2026-01
---
Check git status before touching anything; never overwrite unrelated user changes. For larger changes create a feature branch. Make atomic commits with meaningful messages, one concern each. Before committing: run verification, scan the diff for secrets, review it. NEVER force-push, reset --hard, or clean without explicit approval.

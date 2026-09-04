---
name: systematic-debugging
purpose: Find root causes instead of patching symptoms
task_types: debugging, testing
source: https://github.com/obra/superpowers
attribution: Adapted from obra/superpowers
version: 2026-01
---
Debugging workflow: (1) reproduce the failure with a command, (2) read the actual error, (3) localize to the smallest failing unit, (4) identify the root cause, (5) apply the smallest correct fix, (6) add regression protection (a test), (7) re-verify. NEVER: randomly edit multiple files, suppress type/lint errors without cause, delete or disable tests to get green, or replace whole files when a line-level fix exists.

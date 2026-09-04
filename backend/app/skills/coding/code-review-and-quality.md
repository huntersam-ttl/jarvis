---
name: code-review-and-quality
purpose: Review changes with fresh eyes before completion
task_types: review, verification
source: https://github.com/addyosmani/agent-skills
attribution: Adapted from addyosmani/agent-skills
version: 2026-01
---
Review the actual diff for: correctness, unnecessary complexity, security issues, missed tests, and regressions. Flag CRITICAL (must fix) vs HIGH (must fix or waive) vs MEDIUM/LOW/NIT. Reject suppressions of lint/type/test failures without a written reason.

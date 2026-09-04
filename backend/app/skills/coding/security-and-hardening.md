---
name: security-and-hardening
purpose: Default to secure patterns in all code changes
task_types: security, api, specification
source: https://github.com/addyosmani/agent-skills
attribution: Adapted from addyosmani/agent-skills
version: 2026-01
---
Never hard-code secrets or log sensitive values. Validate and sanitize all external input. Use parameterized queries. Apply least privilege. Check for path traversal, injection, and unsafe deserialization in anything that handles files, URLs, or user data. Never commit credentials.

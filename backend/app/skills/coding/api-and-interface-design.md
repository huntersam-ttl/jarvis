---
name: api-and-interface-design
purpose: Design clear, stable, well-validated interfaces
task_types: api, specification
source: https://github.com/addyosmani/agent-skills
attribution: Adapted from addyosmani/agent-skills
version: 2026-01
---
Validate all inputs at the boundary; return consistent error shapes with meaningful status codes. Keep backward compatibility: extend, never break, existing clients. Document each endpoint's request/response contract. Never leak internals or secrets in responses.

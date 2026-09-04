"""Jarvis-native Skill Registry.

Skills are reusable engineering playbooks (markdown + metadata), loaded
from disk and injected into agent context only when relevant to the task.
Skills are NOT agents and carry no execution logic.
"""
from __future__ import annotations
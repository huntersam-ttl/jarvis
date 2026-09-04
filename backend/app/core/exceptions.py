"""Jarvis domain exceptions."""
from __future__ import annotations


class JarvisError(Exception):
    """Base Jarvis error."""


class ProviderError(JarvisError):
    """A provider call failed."""


class ProviderNotConfiguredError(ProviderError):
    """The provider is missing required configuration (e.g. API key)."""


class ProviderUnreachableError(ProviderError):
    """The provider endpoint could not be reached."""


class ProviderResponseError(ProviderError):
    """The provider returned an error response."""


class ChatError(JarvisError):
    """A chat request failed."""

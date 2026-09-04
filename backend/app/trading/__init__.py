"""Generic Trading Bridge.

Jarvis is the control/monitoring layer around an existing, separately
developed trading agent. The actual trading intelligence lives outside
Jarvis; this package only normalizes its API.

Adapters implement TradingAdapter. Today: MockTradingAdapter (development)
and HTTPTradingAdapter (talks to the real agent over TRADING_AGENT_BASE_URL).
"""

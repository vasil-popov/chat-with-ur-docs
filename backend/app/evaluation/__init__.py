"""Thesis evaluation layer: metrics instrumentation for agent architecture comparison.

This package measures per-run efficiency (latency, LLM calls, token usage, cost,
tool calls, hops) for the supervisor and monolithic agent arms so the thesis can
compare how architecture affects efficiency. Measurement must be exact and fair:
the supervisor's router LLM call is counted alongside the specialist calls.
"""

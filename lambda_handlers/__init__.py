"""AWS Lambda entry points — one file per externally-addressable surface.

``orchestrator_handler`` is the scheduled EventBridge target that runs a full
pass of the deterministic checks and persists whatever the agents propose.
``api_handler`` is the REST surface the dashboard talks to (see
``docs/ARCHITECTURE.md`` §9).
"""

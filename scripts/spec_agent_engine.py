#!/usr/bin/env python
import spec_agent_engine_checks as _checks
import spec_agent_engine_core as _core


def __getattr__(name: str):
    if hasattr(_core, name):
        return getattr(_core, name)
    if hasattr(_checks, name):
        return getattr(_checks, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(list(vars(_core).keys()) + list(vars(_checks).keys())))

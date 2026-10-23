"""Importing this package registers every built-in signal.

To add a signal: create a module here with a @register'ed Signal subclass, import
it below, and give it a weight in ../modes.py.
"""

from . import keywords, laughter, loudness, music, speech  # noqa: F401  (registers)
from .base import REGISTRY, ReasonEvent, Signal, SignalResult, SignalUnavailable, register

__all__ = ["REGISTRY", "ReasonEvent", "Signal", "SignalResult", "SignalUnavailable", "register"]

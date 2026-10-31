"""Exceptions shared by the e-ink dashboard renderer."""

from __future__ import annotations


class RenderNotReady(Exception):
    """A widget's data has not loaded yet: skip this render, keep the last image.

    Raise this only for transient conditions, such as an entity that is
    absent from the states snapshot while Home Assistant is still
    starting.  Genuine faults should raise anything else, so that they
    are still logged in full with a traceback.
    """

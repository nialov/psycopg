"""
psycopg3 types package
"""

# Copyright (C) 2020 The Psycopg Team


from .oids import builtins

# Register default adapters
from . import array, composite, numeric, text  # noqa

__all__ = ["builtins"]

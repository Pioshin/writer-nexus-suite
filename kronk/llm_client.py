"""
Kronk LLMClient — thin re-export from adam_lib.

All logic lives in ../adam_lib/llm_client.py.
This file exists only for import-path compatibility.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from adam_lib.llm_client import LLMClient  # noqa: F401

__all__ = ["LLMClient"]

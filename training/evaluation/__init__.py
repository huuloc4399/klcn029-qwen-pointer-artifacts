"""Offline, versioned evaluation utilities for Qwen CV extraction."""

from .parser import PARSER_VERSION, ParseResult, parse_cvschema_output

__all__ = ["PARSER_VERSION", "ParseResult", "parse_cvschema_output"]

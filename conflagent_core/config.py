"""Configuration loading utilities for Conflagent."""

from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable, Dict

from flask import abort, g


CONFIG_CACHE: Dict[str, Dict[str, Any]] = {}


def load_config(endpoint_name: str) -> Dict[str, Any]:
    """Load configuration for the given endpoint from disk."""
    if endpoint_name in CONFIG_CACHE:
        return CONFIG_CACHE[endpoint_name]

    path = f"../conflagent.{endpoint_name}.properties"
    if not os.path.exists(path):
        abort(404, description=f"Configuration for endpoint '{endpoint_name}' not found")

    config: Dict[str, Any] = {}
    with open(path, "r", encoding="utf-8") as file_handle:
        for line in file_handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if sep:
                config[key.strip()] = value.strip()

    required_keys = [
        "email",
        "api_token",
        "base_url",
        "space_key",
        "root_page_id",
        "gpt_shared_secret",
    ]
    for key in required_keys:
        if key not in config:
            abort(500, description=f"Missing required config key '{key}' in {path}")

    CONFIG_CACHE[endpoint_name] = config
    return config


def with_config(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that injects endpoint configuration into the Flask global."""

    @wraps(func)
    def wrapper(endpoint_name: str, *args: Any, **kwargs: Any):
        g.config = load_config(endpoint_name)
        return func(endpoint_name, *args, **kwargs)

    return wrapper


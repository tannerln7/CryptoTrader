"""Minimal configuration path helpers for the Phase 0 scaffold."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.example.yaml"
DEFAULT_SOURCES_PATH = CONFIG_DIR / "sources.example.yaml"
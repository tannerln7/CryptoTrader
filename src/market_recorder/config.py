"""Typed runtime configuration loading and validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.example.yaml"
DEFAULT_SOURCES_PATH = CONFIG_DIR / "sources.example.yaml"

_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_SUPPORTED_STORAGE_FORMATS = frozenset({"jsonl.zst"})
_SUPPORTED_ROTATIONS = frozenset({"hourly"})


class ConfigError(ValueError):
	"""Raised when recorder configuration is invalid."""


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
	environment: str
	timezone: str
	data_root: Path
	sources_config: Path

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any], *, repo_root: Path) -> "RuntimeConfig":
		environment = _require_str(mapping, "environment", "runtime")
		timezone = _require_str(mapping, "timezone", "runtime")
		if timezone != "UTC":
			raise ConfigError("runtime.timezone must be UTC")

		data_root = _resolve_repo_path(_require_str(mapping, "data_root", "runtime"), repo_root)
		sources_config = _resolve_repo_path(
			_require_str(mapping, "sources_config", "runtime"),
			repo_root,
		)
		return cls(
			environment=environment,
			timezone=timezone,
			data_root=data_root,
			sources_config=sources_config,
		)


@dataclass(frozen=True, slots=True)
class LoggingConfig:
	level: str
	structured: bool

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any]) -> "LoggingConfig":
		level = _require_str(mapping, "level", "logging").upper()
		if level not in _VALID_LOG_LEVELS:
			raise ConfigError(
				f"logging.level must be one of {sorted(_VALID_LOG_LEVELS)}, got {level!r}",
			)
		structured = _require_bool(mapping, "structured", "logging")
		return cls(level=level, structured=structured)


@dataclass(frozen=True, slots=True)
class StorageConfig:
	format: str
	rotation: str

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any]) -> "StorageConfig":
		storage_format = _require_str(mapping, "format", "storage")
		if storage_format not in _SUPPORTED_STORAGE_FORMATS:
			raise ConfigError(
				f"storage.format must be one of {sorted(_SUPPORTED_STORAGE_FORMATS)}, got {storage_format!r}",
			)

		rotation = _require_str(mapping, "rotation", "storage")
		if rotation not in _SUPPORTED_ROTATIONS:
			raise ConfigError(
				f"storage.rotation must be one of {sorted(_SUPPORTED_ROTATIONS)}, got {rotation!r}",
			)
		return cls(format=storage_format, rotation=rotation)


@dataclass(frozen=True, slots=True)
class ValidationConfig:
	enable_sample_checks: bool

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any]) -> "ValidationConfig":
		return cls(enable_sample_checks=_require_bool(mapping, "enable_sample_checks", "validation"))


@dataclass(frozen=True, slots=True)
class PythFeedConfig:
	canonical_symbol: str
	source_symbol: str
	feed_id: str

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any], *, location: str) -> "PythFeedConfig":
		return cls(
			canonical_symbol=_require_str(mapping, "canonical_symbol", location),
			source_symbol=_require_str(mapping, "source_symbol", location),
			feed_id=_require_feed_id(mapping, "feed_id", location),
		)


@dataclass(frozen=True, slots=True)
class PythSourceConfig:
	enabled: bool
	provider: str
	http_base_url: str
	feeds: tuple[PythFeedConfig, ...]

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any]) -> "PythSourceConfig":
		enabled = _require_bool(mapping, "enabled", "pyth")
		feeds = tuple(
			PythFeedConfig.from_mapping(feed, location=f"pyth.feeds[{index}]")
			for index, feed in enumerate(_require_mapping_list(mapping, "feeds", "pyth"))
		)
		if enabled and not feeds:
			raise ConfigError("pyth.feeds must contain at least one feed when pyth.enabled is true")
		return cls(
			enabled=enabled,
			provider=_require_str(mapping, "provider", "pyth"),
			http_base_url=_require_str(mapping, "http_base_url", "pyth"),
			feeds=feeds,
		)


@dataclass(frozen=True, slots=True)
class AsterSymbolConfig:
	canonical_symbol: str
	source_symbol: str

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any], *, location: str) -> "AsterSymbolConfig":
		return cls(
			canonical_symbol=_require_str(mapping, "canonical_symbol", location),
			source_symbol=_require_str(mapping, "source_symbol", location),
		)


@dataclass(frozen=True, slots=True)
class AsterSourceConfig:
	enabled: bool
	rest_base_url: str
	ws_base_url: str
	symbols: tuple[AsterSymbolConfig, ...]
	streams: tuple[str, ...]

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any]) -> "AsterSourceConfig":
		enabled = _require_bool(mapping, "enabled", "aster")
		symbols = tuple(
			AsterSymbolConfig.from_mapping(symbol, location=f"aster.symbols[{index}]")
			for index, symbol in enumerate(_require_mapping_list(mapping, "symbols", "aster"))
		)
		streams = tuple(_require_str_list(mapping, "streams", "aster"))
		if enabled and not symbols:
			raise ConfigError("aster.symbols must contain at least one symbol when aster.enabled is true")
		if enabled and not streams:
			raise ConfigError("aster.streams must contain at least one stream when aster.enabled is true")
		return cls(
			enabled=enabled,
			rest_base_url=_require_str(mapping, "rest_base_url", "aster"),
			ws_base_url=_require_str(mapping, "ws_base_url", "aster"),
			symbols=symbols,
			streams=streams,
		)


@dataclass(frozen=True, slots=True)
class TradingViewWebhookConfig:
	bind_host: str
	bind_port: int
	path: str

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any]) -> "TradingViewWebhookConfig":
		bind_port = _require_int(mapping, "bind_port", "tradingview.webhook")
		if bind_port <= 0 or bind_port > 65535:
			raise ConfigError("tradingview.webhook.bind_port must be between 1 and 65535")

		path = _require_str(mapping, "path", "tradingview.webhook")
		if not path.startswith("/"):
			raise ConfigError("tradingview.webhook.path must start with '/'")

		return cls(
			bind_host=_require_str(mapping, "bind_host", "tradingview.webhook"),
			bind_port=bind_port,
			path=path,
		)


@dataclass(frozen=True, slots=True)
class TradingViewSourceConfig:
	enabled: bool
	webhook: TradingViewWebhookConfig

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any]) -> "TradingViewSourceConfig":
		return cls(
			enabled=_require_bool(mapping, "enabled", "tradingview"),
			webhook=TradingViewWebhookConfig.from_mapping(
				_require_section(mapping, "webhook", "tradingview"),
			),
		)


@dataclass(frozen=True, slots=True)
class SourcesConfig:
	pyth: PythSourceConfig
	aster: AsterSourceConfig
	tradingview: TradingViewSourceConfig

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any]) -> "SourcesConfig":
		return cls(
			pyth=PythSourceConfig.from_mapping(_require_section(mapping, "pyth", "sources")),
			aster=AsterSourceConfig.from_mapping(_require_section(mapping, "aster", "sources")),
			tradingview=TradingViewSourceConfig.from_mapping(
				_require_section(mapping, "tradingview", "sources"),
			),
		)


@dataclass(frozen=True, slots=True)
class RecorderConfig:
	runtime: RuntimeConfig
	logging: LoggingConfig
	storage: StorageConfig
	validation: ValidationConfig
	sources: SourcesConfig
	config_path: Path
	sources_path: Path
	repo_root: Path

	@property
	def enabled_sources(self) -> tuple[str, ...]:
		names: list[str] = []
		if self.sources.pyth.enabled:
			names.append("pyth")
		if self.sources.aster.enabled:
			names.append("aster")
		if self.sources.tradingview.enabled:
			names.append("tradingview")
		return tuple(names)


def load_config(
	config_path: str | Path = DEFAULT_CONFIG_PATH,
	*,
	sources_path: str | Path | None = None,
	repo_root: Path = REPO_ROOT,
) -> RecorderConfig:
	"""Load and validate the runtime and source configuration files."""

	resolved_config_path = _resolve_repo_path(config_path, repo_root)
	config_mapping = _load_yaml_mapping(resolved_config_path, "runtime config")

	runtime = RuntimeConfig.from_mapping(_require_section(config_mapping, "runtime", "config"), repo_root=repo_root)
	logging_config = LoggingConfig.from_mapping(_require_section(config_mapping, "logging", "config"))
	storage = StorageConfig.from_mapping(_require_section(config_mapping, "storage", "config"))
	validation = ValidationConfig.from_mapping(_require_section(config_mapping, "validation", "config"))

	resolved_sources_path = _resolve_repo_path(sources_path or runtime.sources_config, repo_root)
	sources_mapping = _load_yaml_mapping(resolved_sources_path, "sources config")
	sources = SourcesConfig.from_mapping(sources_mapping)

	return RecorderConfig(
		runtime=runtime,
		logging=logging_config,
		storage=storage,
		validation=validation,
		sources=sources,
		config_path=resolved_config_path,
		sources_path=resolved_sources_path,
		repo_root=repo_root,
	)


def _load_yaml_mapping(path: Path, label: str) -> dict[str, Any]:
	try:
		with path.open("r", encoding="utf-8") as handle:
			loaded = yaml.safe_load(handle) or {}
	except FileNotFoundError as exc:
		raise ConfigError(f"{label} file not found: {path}") from exc
	except yaml.YAMLError as exc:
		raise ConfigError(f"Failed to parse {label} file {path}: {exc}") from exc

	if not isinstance(loaded, Mapping):
		raise ConfigError(f"{label} file must contain a top-level mapping: {path}")
	return dict(loaded)


def _resolve_repo_path(value: str | Path, repo_root: Path) -> Path:
	path = Path(value)
	if path.is_absolute():
		return path
	return (repo_root / path).resolve()


def _require_section(mapping: Mapping[str, Any], key: str, location: str) -> Mapping[str, Any]:
	if key not in mapping:
		raise ConfigError(f"Missing required section {location}.{key}")
	value = mapping[key]
	if not isinstance(value, Mapping):
		raise ConfigError(f"{location}.{key} must be a mapping")
	return value


def _require_str(mapping: Mapping[str, Any], key: str, location: str) -> str:
	value = mapping.get(key)
	if not isinstance(value, str) or not value.strip():
		raise ConfigError(f"{location}.{key} must be a non-empty string")
	return value.strip()


def _require_bool(mapping: Mapping[str, Any], key: str, location: str) -> bool:
	value = mapping.get(key)
	if not isinstance(value, bool):
		raise ConfigError(f"{location}.{key} must be a boolean")
	return value


def _require_int(mapping: Mapping[str, Any], key: str, location: str) -> int:
	value = mapping.get(key)
	if isinstance(value, bool) or not isinstance(value, int):
		raise ConfigError(f"{location}.{key} must be an integer")
	return value


def _require_mapping_list(mapping: Mapping[str, Any], key: str, location: str) -> Sequence[Mapping[str, Any]]:
	value = mapping.get(key)
	if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
		raise ConfigError(f"{location}.{key} must be a list")

	items: list[Mapping[str, Any]] = []
	for index, item in enumerate(value):
		if not isinstance(item, Mapping):
			raise ConfigError(f"{location}.{key}[{index}] must be a mapping")
		items.append(item)
	return items


def _require_str_list(mapping: Mapping[str, Any], key: str, location: str) -> tuple[str, ...]:
	value = mapping.get(key)
	if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
		raise ConfigError(f"{location}.{key} must be a list of strings")

	items: list[str] = []
	for index, item in enumerate(value):
		if not isinstance(item, str) or not item.strip():
			raise ConfigError(f"{location}.{key}[{index}] must be a non-empty string")
		items.append(item.strip())
	return tuple(items)


def _require_feed_id(mapping: Mapping[str, Any], key: str, location: str) -> str:
	value = mapping.get(key)
	if isinstance(value, bool):
		raise ConfigError(f"{location}.{key} must be a hex string or positive integer")

	if isinstance(value, int):
		if value < 0:
			raise ConfigError(f"{location}.{key} must be a positive integer when provided numerically")
		return hex(value)

	if not isinstance(value, str) or not value.strip():
		raise ConfigError(f"{location}.{key} must be a non-empty hex string or positive integer")

	normalized = value.strip().lower()
	if normalized.startswith("0x"):
		normalized = normalized[2:]

	try:
		int(normalized, 16)
	except ValueError as exc:
		raise ConfigError(f"{location}.{key} must be a valid hexadecimal feed id") from exc

	return f"0x{normalized}"
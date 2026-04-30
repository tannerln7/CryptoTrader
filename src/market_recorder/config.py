"""Typed runtime configuration loading and validation."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path.cwd().resolve()
CONFIG_DIR = Path("config")
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.example.yaml"
DEFAULT_SOURCES_PATH = CONFIG_DIR / "sources.example.yaml"

_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_SUPPORTED_STORAGE_FORMATS = frozenset({"jsonl.zst"})
_SUPPORTED_LEGACY_ROTATIONS = frozenset({"hourly"})


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
class RotationPolicyConfig:
	max_age_seconds: int
	max_bytes: int | None

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any], *, location: str) -> "RotationPolicyConfig":
		max_age_seconds = _require_int(mapping, "max_age_seconds", location)
		if max_age_seconds <= 0:
			raise ConfigError(f"{location}.max_age_seconds must be a positive integer")

		max_bytes = _optional_int(mapping, "max_bytes", location)
		if max_bytes is not None and max_bytes <= 0:
			raise ConfigError(f"{location}.max_bytes must be a positive integer when provided")

		return cls(max_age_seconds=max_age_seconds, max_bytes=max_bytes)

	@classmethod
	def hourly_default(cls) -> "RotationPolicyConfig":
		return cls(max_age_seconds=3600, max_bytes=None)


@dataclass(frozen=True, slots=True)
class ManualRotationConfig:
	enabled: bool
	require_reason: bool
	min_age_seconds: int
	min_bytes: int
	cooldown_seconds: int

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any], *, location: str) -> "ManualRotationConfig":
		enabled = _require_bool_with_default(mapping, "enabled", location, default=False)
		require_reason = _require_bool_with_default(mapping, "require_reason", location, default=True)
		min_age_seconds = _require_int_with_default(mapping, "min_age_seconds", location, default=300)
		if min_age_seconds < 0:
			raise ConfigError(f"{location}.min_age_seconds must be zero or a positive integer")
		min_bytes = _require_int_with_default(mapping, "min_bytes", location, default=0)
		if min_bytes < 0:
			raise ConfigError(f"{location}.min_bytes must be zero or a positive integer")
		cooldown_seconds = _require_int_with_default(mapping, "cooldown_seconds", location, default=300)
		if cooldown_seconds < 0:
			raise ConfigError(f"{location}.cooldown_seconds must be zero or a positive integer")
		return cls(
			enabled=enabled,
			require_reason=require_reason,
			min_age_seconds=min_age_seconds,
			min_bytes=min_bytes,
			cooldown_seconds=cooldown_seconds,
		)

	@classmethod
	def defaults(cls) -> "ManualRotationConfig":
		return cls(
			enabled=False,
			require_reason=True,
			min_age_seconds=300,
			min_bytes=0,
			cooldown_seconds=300,
		)


@dataclass(frozen=True, slots=True)
class StorageRotationConfig:
	default: RotationPolicyConfig
	classes: dict[str, RotationPolicyConfig]
	stream_classes: dict[str, dict[str, str]]
	manual_rotation: ManualRotationConfig
	uses_legacy_hourly: bool = False

	@classmethod
	def from_value(cls, value: Any) -> "StorageRotationConfig":
		if isinstance(value, str):
			rotation_name = value.strip()
			if rotation_name not in _SUPPORTED_LEGACY_ROTATIONS:
				raise ConfigError(
					f"storage.rotation must be one of {sorted(_SUPPORTED_LEGACY_ROTATIONS)} or a mapping, got {rotation_name!r}",
				)
			return cls(
				default=RotationPolicyConfig.hourly_default(),
				classes={},
				stream_classes={},
				manual_rotation=ManualRotationConfig.defaults(),
				uses_legacy_hourly=True,
			)

		if not isinstance(value, Mapping):
			raise ConfigError("storage.rotation must be either a string or a mapping")

		default = RotationPolicyConfig.from_mapping(
			_require_section(value, "default", "storage.rotation"),
			location="storage.rotation.default",
		)

		class_section = _optional_section(value, "classes", "storage.rotation", default={})
		classes: dict[str, RotationPolicyConfig] = {}
		for raw_class_name, raw_policy in class_section.items():
			if not isinstance(raw_class_name, str) or not raw_class_name.strip():
				raise ConfigError("storage.rotation.classes keys must be non-empty strings")
			class_name = raw_class_name.strip()
			if not isinstance(raw_policy, Mapping):
				raise ConfigError(f"storage.rotation.classes.{class_name} must be a mapping")
			classes[class_name] = RotationPolicyConfig.from_mapping(
				raw_policy,
				location=f"storage.rotation.classes.{class_name}",
			)

		stream_class_section = _optional_section(value, "stream_classes", "storage.rotation", default={})
		stream_classes: dict[str, dict[str, str]] = {}
		for raw_source_name, raw_assignments in stream_class_section.items():
			if not isinstance(raw_source_name, str) or not raw_source_name.strip():
				raise ConfigError("storage.rotation.stream_classes keys must be non-empty strings")
			source_name = raw_source_name.strip()
			if not isinstance(raw_assignments, Mapping):
				raise ConfigError(f"storage.rotation.stream_classes.{source_name} must be a mapping")
			assignments: dict[str, str] = {}
			for raw_stream_name, raw_class_name in raw_assignments.items():
				if not isinstance(raw_stream_name, str) or not raw_stream_name.strip():
					raise ConfigError(
						f"storage.rotation.stream_classes.{source_name} keys must be non-empty strings",
					)
				if not isinstance(raw_class_name, str) or not raw_class_name.strip():
					raise ConfigError(
						f"storage.rotation.stream_classes.{source_name}.{raw_stream_name} must be a non-empty string",
					)
				assignments[raw_stream_name.strip()] = raw_class_name.strip()
			stream_classes[source_name] = assignments

		for source_name, assignments in stream_classes.items():
			for stream_name, class_name in assignments.items():
				if class_name not in classes:
					raise ConfigError(
						f"storage.rotation.stream_classes.{source_name}.{stream_name} references undefined rotation class {class_name!r}",
					)

		manual_rotation = ManualRotationConfig.from_mapping(
			_optional_section(value, "manual_rotation", "storage.rotation", default={}),
			location="storage.rotation.manual_rotation",
		)

		return cls(
			default=default,
			classes=classes,
			stream_classes=stream_classes,
			manual_rotation=manual_rotation,
		)

	def resolve_policy(self, *, source: str, stream: str) -> RotationPolicyConfig:
		source_assignments = self.stream_classes.get(source, {})
		for stream_key in (stream, _normalize_rotation_stream_key(stream)):
			class_name = source_assignments.get(stream_key)
			if class_name is not None:
				return self.classes[class_name]
		return self.default


@dataclass(frozen=True, slots=True)
class StorageConfig:
	format: str
	rotation: StorageRotationConfig
	compression_level: int

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any]) -> "StorageConfig":
		storage_format = _require_str(mapping, "format", "storage")
		if storage_format not in _SUPPORTED_STORAGE_FORMATS:
			raise ConfigError(
				f"storage.format must be one of {sorted(_SUPPORTED_STORAGE_FORMATS)}, got {storage_format!r}",
			)

		if "rotation" not in mapping:
			raise ConfigError("storage.rotation is required")
		rotation = StorageRotationConfig.from_value(mapping["rotation"])

		compression_level = _require_int(mapping, "compression_level", "storage")
		if compression_level <= 0:
			raise ConfigError("storage.compression_level must be a positive integer")

		return cls(
			format=storage_format,
			rotation=rotation,
			compression_level=compression_level,
		)

	def resolve_rotation_policy(self, *, source: str, stream: str) -> RotationPolicyConfig:
		return self.rotation.resolve_policy(source=source, stream=stream)


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
class AsterDepthConfig:
	snapshot_limit: int
	snapshot_interval_seconds: int

	@classmethod
	def from_mapping(cls, mapping: Mapping[str, Any], *, location: str) -> "AsterDepthConfig":
		snapshot_limit = _require_int(mapping, "snapshot_limit", location)
		if snapshot_limit <= 0:
			raise ConfigError(f"{location}.snapshot_limit must be a positive integer")

		snapshot_interval_seconds = _require_int(mapping, "snapshot_interval_seconds", location)
		if snapshot_interval_seconds <= 0:
			raise ConfigError(f"{location}.snapshot_interval_seconds must be a positive integer")

		return cls(
			snapshot_limit=snapshot_limit,
			snapshot_interval_seconds=snapshot_interval_seconds,
		)


@dataclass(frozen=True, slots=True)
class AsterSourceConfig:
	enabled: bool
	rest_base_url: str
	ws_base_url: str
	symbols: tuple[AsterSymbolConfig, ...]
	streams: tuple[str, ...]
	depth: AsterDepthConfig

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
		depth = AsterDepthConfig.from_mapping(
			_optional_section(
				mapping,
				"depth",
				"aster",
				default={"snapshot_limit": 1000, "snapshot_interval_seconds": 300},
			),
			location="aster.depth",
		)
		return cls(
			enabled=enabled,
			rest_base_url=_require_str(mapping, "rest_base_url", "aster"),
			ws_base_url=_require_str(mapping, "ws_base_url", "aster"),
			symbols=symbols,
			streams=streams,
			depth=depth,
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
	config_path: str | Path | None = None,
	*,
	sources_path: str | Path | None = None,
	repo_root: Path | None = None,
) -> RecorderConfig:
	"""Load and validate the runtime and source configuration files."""

	resolved_repo_root = _resolve_repo_root(repo_root, config_path)
	resolved_config_path = _resolve_repo_path(config_path or DEFAULT_CONFIG_PATH, resolved_repo_root)
	config_mapping = _load_yaml_mapping(resolved_config_path, "runtime config")

	runtime = RuntimeConfig.from_mapping(
		_require_section(config_mapping, "runtime", "config"),
		repo_root=resolved_repo_root,
	)
	logging_config = LoggingConfig.from_mapping(_require_section(config_mapping, "logging", "config"))
	storage = StorageConfig.from_mapping(_require_section(config_mapping, "storage", "config"))
	validation = ValidationConfig.from_mapping(_require_section(config_mapping, "validation", "config"))

	resolved_sources_path = _resolve_repo_path(sources_path or runtime.sources_config, resolved_repo_root)
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
		repo_root=resolved_repo_root,
	)


def apply_runtime_overrides(
	config: RecorderConfig,
	*,
	data_root: str | Path | None = None,
	log_level: str | None = None,
) -> RecorderConfig:
	runtime = config.runtime
	logging_config = config.logging

	if data_root is not None:
		runtime = replace(
			runtime,
			data_root=_resolve_repo_path(data_root, config.repo_root),
		)

	if log_level is not None:
		normalized_level = log_level.strip().upper()
		if normalized_level not in _VALID_LOG_LEVELS:
			raise ConfigError(
				f"logging.level must be one of {sorted(_VALID_LOG_LEVELS)}, got {normalized_level!r}",
			)
		logging_config = replace(logging_config, level=normalized_level)

	if runtime is config.runtime and logging_config is config.logging:
		return config

	return replace(
		config,
		runtime=runtime,
		logging=logging_config,
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


def _resolve_repo_root(repo_root: Path | None, config_path: str | Path | None) -> Path:
	if repo_root is not None:
		return Path(repo_root).resolve()

	env_repo_root = os.environ.get("MARKET_RECORDER_REPO_ROOT")
	if env_repo_root:
		return Path(env_repo_root).resolve()

	search_start = Path.cwd().resolve()
	if config_path is not None:
		candidate_path = Path(config_path)
		if candidate_path.is_absolute():
			search_start = candidate_path.resolve().parent

	for candidate in (search_start, *search_start.parents):
		if (candidate / "pyproject.toml").is_file() and (candidate / DEFAULT_CONFIG_PATH).is_file():
			return candidate.resolve()

	return search_start


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


def _optional_section(
	mapping: Mapping[str, Any],
	key: str,
	location: str,
	*,
	default: Mapping[str, Any],
) -> Mapping[str, Any]:
	if key not in mapping:
		return default
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


def _optional_int(mapping: Mapping[str, Any], key: str, location: str) -> int | None:
	if key not in mapping:
		return None
	value = mapping[key]
	if value is None:
		return None
	if isinstance(value, bool) or not isinstance(value, int):
		raise ConfigError(f"{location}.{key} must be an integer when provided")
	return value


def _require_int_with_default(mapping: Mapping[str, Any], key: str, location: str, *, default: int) -> int:
	if key not in mapping:
		return default
	return _require_int(mapping, key, location)


def _require_bool_with_default(
	mapping: Mapping[str, Any],
	key: str,
	location: str,
	*,
	default: bool,
) -> bool:
	if key not in mapping:
		return default
	return _require_bool(mapping, key, location)


def _normalize_rotation_stream_key(stream_name: str) -> str:
	return stream_name.strip().replace("@", "_").replace("/", "_")


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
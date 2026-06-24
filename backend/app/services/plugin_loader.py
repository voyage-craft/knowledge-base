"""Plugin loader — scans, validates, and dynamically loads workflow plugins.

Architecture:
  plugins/
    builtin/         # Shipped with the system, read-only
    third_party/     # User-installed via upload (.kbplugin)

Each plugin directory must contain a `plugin.json` manifest and a Python entry
file (default `processor.py`) that exports a class inheriting from NodeProcessor.
"""

import importlib
import json
import logging
import os
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.version import SYSTEM_VERSION, version_matches, MANIFEST_SCHEMA_VERSION

logger = logging.getLogger(__name__)

# ── Paths ──
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
PLUGINS_ROOT = _BACKEND_DIR / "plugins"
BUILTIN_DIR = PLUGINS_ROOT / "builtin"
THIRD_PARTY_DIR = PLUGINS_ROOT / "third_party"


# ── Manifest Schema (Pydantic) ──

class ConfigField(BaseModel):
    """A single configuration field in a plugin's config schema."""
    key: str
    label: str
    type: str = "text"  # text | select | textarea | number
    options: Optional[list[str]] = None
    default: Optional[str] = None
    placeholder: Optional[str] = None
    advanced: bool = False  # If True, shown in "Advanced" section


class ConfigSchema(BaseModel):
    """Plugin configuration schema."""
    fields: list[ConfigField] = Field(default_factory=list)


class PluginManifest(BaseModel):
    """Validated plugin.json manifest."""
    id: str
    name: str
    version: str
    min_system_version: str = "0.0.0"
    max_system_version: str = "99.x"
    description: str = ""
    author: str = ""
    category: str = "process"  # input | process | output
    icon: str = "Sparkles"
    color: str = "bg-blue-500"
    node_type: str = ""
    entry: str = "processor.py"
    configurable: bool = False
    config_schema: Optional[ConfigSchema] = None
    dependencies: dict = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)
    changelog: dict[str, str] = Field(default_factory=dict)
    plugin_api_version: str = "1.0"
    manifest_version: int = MANIFEST_SCHEMA_VERSION


# ── Loaded Plugin Info ──

@dataclass
class LoadedPlugin:
    """Runtime info for a successfully loaded plugin."""
    manifest: PluginManifest
    path: Path                        # Plugin directory path
    is_builtin: bool
    is_compatible: bool = True
    compatibility_message: str = ""
    processor_class: Any = None       # The NodeProcessor subclass
    error: Optional[str] = None


# ── Plugin Loader Singleton ──

class PluginLoader:
    """Singleton that manages plugin discovery, validation, and loading."""

    _instance: Optional["PluginLoader"] = None
    _plugins: dict[str, LoadedPlugin] = {}
    _loaded: bool = False

    def __new__(cls) -> "PluginLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def plugins(self) -> dict[str, LoadedPlugin]:
        return dict(self._plugins)

    def get_plugin(self, plugin_id: str) -> Optional[LoadedPlugin]:
        return self._plugins.get(plugin_id)

    def get_compatible_plugins(self) -> list[LoadedPlugin]:
        return [p for p in self._plugins.values() if p.is_compatible and p.error is None]

    def get_all_manifests(self) -> list[dict]:
        """Return frontend-friendly manifest list for all loaded plugins."""
        result = []
        for p in self._plugins.values():
            m = p.manifest
            result.append({
                "id": m.id,
                "plugin_id": m.id,
                "name": m.name,
                "version": m.version,
                "description": m.description,
                "author": m.author,
                "category": m.category,
                "icon": m.icon,
                "color": m.color,
                "node_type": m.node_type or m.id.split(".")[-1],
                "configurable": m.configurable,
                "config_schema": m.config_schema.model_dump() if m.config_schema else None,
                "is_builtin": p.is_builtin,
                "is_compatible": p.is_compatible,
                "compatibility_message": p.compatibility_message,
                "is_active": p.is_compatible and p.error is None,
                "error": p.error,
                "permissions": m.permissions,
                "changelog": m.changelog,
            })
        return result

    # ── Loading ──

    def load_all(self) -> dict[str, LoadedPlugin]:
        """Scan and load all plugins from builtin and third_party directories."""
        if self._loaded:
            return self._plugins

        self._plugins.clear()

        # Ensure directories exist
        BUILTIN_DIR.mkdir(parents=True, exist_ok=True)
        THIRD_PARTY_DIR.mkdir(parents=True, exist_ok=True)

        # Load builtin first (higher priority)
        self._scan_directory(BUILTIN_DIR, is_builtin=True)
        # Then third-party
        self._scan_directory(THIRD_PARTY_DIR, is_builtin=False)

        self._loaded = True

        loaded_count = sum(1 for p in self._plugins.values() if p.error is None)
        total = len(self._plugins)
        logger.info("Plugin loader: %d/%d plugins loaded successfully", loaded_count, total)

        return self._plugins

    def reload(self) -> dict[str, LoadedPlugin]:
        """Force reload all plugins (for development / after install)."""
        self._loaded = False
        return self.load_all()

    def _scan_directory(self, directory: Path, is_builtin: bool) -> None:
        """Scan a plugin directory for subdirectories containing plugin.json."""
        if not directory.is_dir():
            return

        for entry in sorted(directory.iterdir()):
            if not entry.is_dir():
                continue

            manifest_path = entry / "plugin.json"
            if not manifest_path.is_file():
                logger.warning("Plugin dir %s has no plugin.json, skipping", entry.name)
                continue

            self._load_plugin(entry, manifest_path, is_builtin)

    def _load_plugin(self, plugin_dir: Path, manifest_path: Path, is_builtin: bool) -> None:
        """Load a single plugin from its directory."""
        # Parse manifest
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            manifest = PluginManifest(**raw)
        except Exception as e:
            logger.error("Failed to parse %s: %s", manifest_path, e)
            return

        # Check version compatibility
        compatible = True
        compat_msg = ""
        if not version_matches(SYSTEM_VERSION, manifest.min_system_version, manifest.max_system_version):
            compatible = False
            compat_msg = (
                f"系统版本 {SYSTEM_VERSION} 不在插件要求的 "
                f"[{manifest.min_system_version}, {manifest.max_system_version}] 范围内"
            )

        # Import processor module
        processor_class = None
        error = None
        if compatible:
            processor_class, error = self._import_processor(plugin_dir, manifest)

        loaded = LoadedPlugin(
            manifest=manifest,
            path=plugin_dir,
            is_builtin=is_builtin,
            is_compatible=compatible,
            compatibility_message=compat_msg,
            processor_class=processor_class,
            error=error,
        )

        # Register to NodeProcessorRegistry if processor loaded successfully
        if processor_class and not error:
            node_type = manifest.node_type or manifest.id.split(".")[-1]
            try:
                from app.services.workflow.node_registry import NodeProcessorRegistry
                NodeProcessorRegistry.register_with_metadata(
                    node_type=node_type,
                    processor_cls=processor_class,
                    plugin_id=manifest.id,
                    version=manifest.version,
                    is_builtin=is_builtin,
                )
                logger.debug("Registered plugin processor: %s -> %s", node_type, processor_class.__name__)
            except Exception as e:
                logger.error("Failed to register processor for %s: %s", manifest.id, e)
                loaded.error = str(e)

        self._plugins[manifest.id] = loaded

    def _import_processor(self, plugin_dir: Path, manifest: PluginManifest) -> tuple[Any, Optional[str]]:
        """Dynamically import the processor module from a plugin directory."""
        entry_file = plugin_dir / manifest.entry
        if not entry_file.is_file():
            return None, f"Entry file not found: {manifest.entry}"

        # Add plugin dir to sys.path temporarily
        plugin_dir_str = str(plugin_dir)
        added_to_path = False
        if plugin_dir_str not in sys.path:
            sys.path.insert(0, plugin_dir_str)
            added_to_path = True

        try:
            # Build module name from entry file
            module_name = manifest.entry.replace("/", ".").replace("\\", ".").removesuffix(".py")
            # Use unique module name to avoid conflicts
            unique_name = f"plugin_{manifest.id.replace('.', '_')}_{module_name}"

            spec = importlib.util.spec_from_file_location(unique_name, str(entry_file))
            if spec is None or spec.loader is None:
                return None, f"Cannot create module spec from {entry_file}"

            module = importlib.util.module_from_spec(spec)
            sys.modules[unique_name] = module
            spec.loader.exec_module(module)

            # Find the NodeProcessor subclass in the module
            from app.services.workflow.node_registry import NodeProcessor
            processor_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, NodeProcessor)
                    and attr is not NodeProcessor
                ):
                    processor_class = attr
                    break

            if processor_class is None:
                return None, f"No NodeProcessor subclass found in {manifest.entry}"

            return processor_class, None

        except Exception as e:
            logger.error("Failed to import processor from %s: %s", plugin_dir, e)
            return None, str(e)
        finally:
            if added_to_path and plugin_dir_str in sys.path:
                sys.path.remove(plugin_dir_str)

    # ── Third-Party Install / Uninstall ──

    def install_from_zip(self, zip_path: Path) -> LoadedPlugin:
        """Install a third-party plugin from a .kbplugin (zip) file."""
        THIRD_PARTY_DIR.mkdir(parents=True, exist_ok=True)

        # Extract to temp location first to read manifest
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Validate zip member paths to prevent path traversal attacks
                tmp_resolved = tmp_path.resolve()
                for member in zf.namelist():
                    member_path = (tmp_path / member).resolve()
                    if not str(member_path).startswith(str(tmp_resolved)):
                        raise ValueError(f"Path traversal detected in plugin archive: {member}")
                zf.extractall(tmp_path)

            # Find plugin.json (may be in root or one level deep)
            manifest_candidates = list(tmp_path.rglob("plugin.json"))
            if not manifest_candidates:
                raise ValueError("No plugin.json found in archive")

            manifest_path = manifest_candidates[0]
            plugin_src_dir = manifest_path.parent

            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = PluginManifest(**json.load(f))

            # Check for duplicate builtin plugin
            if manifest.id in self._plugins and self._plugins[manifest.id].is_builtin:
                raise ValueError(f"Cannot overwrite builtin plugin: {manifest.id}")

            # Copy to third_party directory
            dest_dir = THIRD_PARTY_DIR / plugin_src_dir.name
            if dest_dir.exists():
                import shutil
                shutil.rmtree(dest_dir)

            import shutil
            shutil.copytree(plugin_src_dir, dest_dir)

        # Reload to pick up new plugin
        self._loaded = False
        self.load_all()

        plugin = self._plugins.get(manifest.id)
        if not plugin:
            raise RuntimeError(f"Plugin {manifest.id} was installed but failed to load")

        return plugin

    def uninstall(self, plugin_id: str) -> bool:
        """Uninstall a third-party plugin (cannot uninstall builtins)."""
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        if plugin.is_builtin:
            raise ValueError("Cannot uninstall builtin plugins")

        # Unregister the node processor before deleting files
        node_type = plugin.manifest.node_type or plugin.manifest.id.split(".")[-1]
        from app.services.workflow.node_registry import NodeProcessorRegistry
        NodeProcessorRegistry.unregister(node_type)

        import shutil
        shutil.rmtree(plugin.path, ignore_errors=True)

        del self._plugins[plugin_id]
        return True


# ── Singleton Access ──
plugin_loader = PluginLoader()

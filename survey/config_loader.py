"""Load a survey configuration from a Python or YAML file."""
import importlib.util
from pathlib import Path


def _load_python_config(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Python config from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "build_config"):
        config = module.build_config()
    elif hasattr(module, "CONFIG"):
        config = module.CONFIG
    else:
        raise RuntimeError(f"{path} must define CONFIG or build_config()")
    if not isinstance(config, dict):
        raise RuntimeError(f"{path} did not return a dict configuration")
    return config


def _load_yaml_config(path):
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PyYAML is required for .yaml/.yml files. "
            "Use a .py config to avoid the dependency."
        ) from exc
    with path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    if not isinstance(config, dict):
        raise RuntimeError(f"{path} did not contain a dict configuration")
    return config


def load_config(path):
    config_path = Path(path)
    suffix = config_path.suffix.lower()
    if suffix == ".py":
        return _load_python_config(config_path)
    if suffix in (".yaml", ".yml"):
        return _load_yaml_config(config_path)
    raise RuntimeError(f"Unsupported config suffix {config_path.suffix!r}")

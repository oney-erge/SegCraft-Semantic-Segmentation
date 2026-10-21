"""SegCraft package."""

from importlib.metadata import PackageNotFoundError, version as _distribution_version

from .api import evaluate, list_available_presets, load_config, load_config_object, predict, train
from .config import SegCraftConfig

try:
    __version__ = _distribution_version("segcraft")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "unknown"

__all__ = [
    "SegCraftConfig",
    "__version__",
    "evaluate",
    "list_available_presets",
    "load_config",
    "load_config_object",
    "predict",
    "train",
]

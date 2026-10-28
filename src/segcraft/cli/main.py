"""Command line interface for SegCraft."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Dict

from segcraft import __version__, evaluate, load_config, predict, train
from segcraft.config.loader import resolve_config_path
from segcraft.runtime import collect_runtime_diagnostics, format_runtime_diagnostics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="segcraft",
        description="SegCraft: config-driven semantic segmentation framework",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["validate", "train", "evaluate", "predict", "doctor"],
        default="validate",
        help="Execution mode. Default is validate.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Base config YAML. Defaults to configs/base.yaml when present, "
            "otherwise uses the packaged base config."
        ),
    )
    parser.add_argument(
        "--preset",
        type=Path,
        default=None,
        help="Optional preset name or YAML path (e.g. fast_dev or configs/presets/fast_dev.yaml).",
    )
    parser.add_argument(
        "--local",
        type=Path,
        default=None,
        help="Machine-local override YAML; an explicitly supplied path must exist.",
    )
    parser.add_argument("--print-config", action="store_true")
    parser.add_argument("--version", action="version", version=f"segcraft {__version__}")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "doctor":
        print(format_runtime_diagnostics(collect_runtime_diagnostics()))
        return

    local_path = args.local
    if local_path is None and Path("configs/local.yaml").exists():
        local_path = Path("configs/local.yaml")

    with resolve_config_path(args.config) as config_path:
        config = load_config(config_path, preset_path=args.preset, local_path=local_path)
        if args.print_config:
            print(json.dumps(config, indent=2))

        handlers: Dict[str, Callable[..., Dict[str, Any]]] = {
            "train": train,
            "evaluate": evaluate,
            "predict": predict,
        }

        if args.mode == "validate":
            print("SegCraft config is valid.")
            return

        summary = handlers[args.mode](config_path, preset_path=args.preset, local_path=local_path)
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

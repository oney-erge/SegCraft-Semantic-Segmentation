<p align="center">
  <img src="https://raw.githubusercontent.com/oney-erge/SegCraft-Semantic-Segmentation/main/assets/segcraft-logo.svg" width="96" height="96" alt="SegCraft logo" />
</p>

<h1 align="center">SegCraft</h1>

<p align="center"><strong>Train, evaluate, and run semantic segmentation from one YAML configuration.</strong></p>

<p align="center">
  <a href="https://github.com/oney-erge/SegCraft-Semantic-Segmentation/actions/workflows/ci.yml"><img src="https://github.com/oney-erge/SegCraft-Semantic-Segmentation/actions/workflows/ci.yml/badge.svg" alt="CI status" /></a>
  <a href="https://pypi.org/project/segcraft/"><img src="https://img.shields.io/pypi/v/segcraft.svg" alt="PyPI version" /></a>
  <a href="LICENSE.md"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license" /></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+" />
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/oney-erge/SegCraft-Semantic-Segmentation/main/assets/segcraft-gpu-demo.gif" alt="SegCraft GPU demo: original dashcam video beside semantic segmentation overlay" width="860" />
</p>

SegCraft uses the same YAML setup for training, evaluation, image prediction,
and video prediction. Choose a preset, run it through the CLI, Python API, or
web app, and keep the same configuration across the workflow.

> SegCraft is alpha software. Its Python API and configuration schema can still
> change.

## Quick start

```bash
pip install "segcraft[web]"
segcraft-web          # open http://127.0.0.1:8000
```

Upload a video or provide a YouTube URL, choose a preset, and download the
original, overlay, and side-by-side output videos. By default,
`runtime.device: auto` uses an NVIDIA GPU when a CUDA-enabled PyTorch build is
available and falls back to CPU otherwise.

From a checkout, the launchers set up the environment and open the app:

```bash
./run.sh       # Linux; macOS: ./run.command
```

On Windows, use `.\run.bat`. When it finds an NVIDIA GPU it installs the matching
CUDA build of PyTorch for you (a large download the first time; set
`SEGCRAFT_CPU_ONLY=1` to keep the CPU build). With `pip`, install the
CUDA-enabled PyTorch wheel that matches your system first. Run `segcraft doctor`
to confirm what Torch and CUDA can see.

## What it does

- Train, evaluate, and predict with one configuration merge order: base YAML,
  optional preset, then optional local overrides.
- Use TorchVision, segmentation-models-pytorch, or Hugging Face SegFormer
  models through one interface.
- Run image or video prediction. Video output includes `original.mp4`,
  `overlay.mp4`, `comparison.mp4`, and `summary.json`.
- Use the same presets in the CLI, Python API, and web app.
- Validate configuration and inspect the actual Torch, CUDA, and device state
  with `segcraft validate` and `segcraft doctor`.

## Common commands

```bash
segcraft validate
segcraft predict --preset cityscapes_video --local configs/local.yaml
segcraft train --preset fast_dev --local configs/local.yaml
segcraft evaluate --preset quality --local configs/local.yaml
```

`configs/local.yaml` is for machine-specific paths and is ignored by Git.
Start from `configs/local.example.yaml`.

Useful presets include `fast_dev` for a small CPU training run,
`binary_quickstart` for foreground/background work, and the Cityscapes,
ADE20K, PASCAL VOC, and SMP examples. `task.num_classes` controls the
trainable model head; `task.class_names` only controls display labels.

## Python and notebooks

```python
from segcraft import load_config
from segcraft.prediction import run_prediction

config = load_config("configs/base.yaml", preset_path="cityscapes_video")
summary = run_prediction(config)
```

The notebooks provide a [quick start](notebooks/01_quickstart.ipynb),
[configuration and API guide](notebooks/02_config_and_api.ipynb), and
[web-app guide](notebooks/03_web_app.ipynb).

For optional model extras, Docker, presets, output formats, and development
setup, see the [installation and reference guide](docs/GUIDE.md).
Changes are recorded in the
[Changelog](CHANGELOG.md).

MIT licensed. Built by [Oney Erge](https://oneyerge.com).

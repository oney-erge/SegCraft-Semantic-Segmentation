# Contributing

SegCraft is a configuration-first semantic-segmentation toolkit. The same merged YAML
configuration drives training, evaluation, image and video prediction, the Python API, and the
web app, so a change in one place usually needs to hold in all of them.

## Set up a development checkout

```bash
git clone https://github.com/oney-erge/SegCraft-Semantic-Segmentation.git
cd SegCraft-Semantic-Segmentation
pip install -e ".[web,dev]"      # or: uv sync --frozen --extra web --extra dev
```

On Windows, `.\run.bat` prepares a managed environment and starts the web app instead. With an
NVIDIA GPU it installs the matching CUDA build of PyTorch; `SEGCRAFT_CPU_ONLY=1` keeps the CPU
build. See the [installation and reference guide](docs/GUIDE.md) for the other routes.

## Check your change

```bash
segcraft validate     # the merged configuration still loads
segcraft doctor       # what Torch and CUDA can see on this machine
pytest                # the test suite (CPU, no downloads)
```

If you touched packaging, also run `python -m build` and `twine check dist/*`. If you touched a
launcher (`run.bat`, `run.ps1`, `run.sh`, `run.command`), run `bash -n run.sh run.command` and, on
Windows, `powershell -NoProfile -File scripts/test-launcher-helpers.ps1`. CI runs these on every
pull request, including the launcher helpers under Windows PowerShell 5.1.

## Pull request expectations

- Keep the CLI, Python API, and web app aligned around the same configuration loader and preset
  resolution. Configuration merges in this order: `configs/base.yaml`, an optional preset, then
  the ignored `configs/local.yaml`.
- `task.num_classes` controls the model head; `task.class_names` only controls display labels.
- Keep `runtime.device: auto` falling back to CPU, and report the real Torch and CUDA state rather
  than assuming a GPU.
- Keep optional model ecosystems (Hugging Face, segmentation-models-pytorch, video, web) behind
  their extras. Core configuration parsing must not need Torch.
- Tests must be deterministic: no network access, model downloads, YouTube, or GPU requirements.
  Make any such test opt-in and explicit.
- Keep prediction outputs (`original.mp4`, `overlay.mp4`, `comparison.mp4`, `summary.json`)
  compatible, or say clearly in the pull request that they changed.
- Do not commit local paths, datasets, outputs, downloaded weights, build artifacts, notebook
  output, or large generated media. `configs/local.yaml` is ignored for exactly this reason.
- Add a line to `CHANGELOG.md` under "Unreleased" for any change a user could notice.

## Reporting problems

Use the issue templates for bugs and feature requests. For anything security-related, read
[SECURITY.md](SECURITY.md) first and do not post details in a public issue.

## Summary

-

## Checks

- [ ] `segcraft validate`
- [ ] `pytest`
- [ ] Launcher changes: `bash -n run.sh run.command` and `scripts/test-launcher-helpers.ps1`
- [ ] Packaging changes: `python -m build` and `twine check dist/*`

## Project rules

- [ ] The CLI, Python API, and web app still share one configuration loader.
- [ ] No local paths, datasets, outputs, weights, or large media are committed.
- [ ] Tests do not need the network, a model download, or a GPU.
- [ ] `CHANGELOG.md` has a line under "Unreleased" if a user could notice the change.

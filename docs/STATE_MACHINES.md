# Lifecycle boundaries

- The web app's `JOBS_LOCK` owns admission, cancellation, and terminal job decisions in one server process. A cancellation accepted before completion or failure is committed wins; a later cancellation observes the committed terminal state. Resource-heavy web jobs are admitted one at a time.
- Each new web job writes an atomic `job.json` manifest in its job directory. At startup, queued/running/canceling jobs are marked `interrupted`; the app never automatically reruns them. The browser keeps the last job id for reconnect and distinguishes connection loss from job failure.
- Final video and JSON files are verified before the manifest publishes them as available. Downloads require the committed artifact entry and unchanged file size and modification time. A filename without a committed entry is not offered. Old output folders without a manifest remain untouched and unverified.
- Training checkpoints record the early-stopping counter and are atomically replaced. Older checkpoints without this field still load, with `resume_early_stopping_state` identifying that the counter was unavailable. This is continuation of recorded control state, not a promise of bitwise reproducibility.

`tests/test_webapp.py` and `tests/test_training_checkpoint.py` cover key boundaries. File manifests and Python locks do not coordinate separate server processes; run one web-app worker. A downgrade to a version that ignores manifests can restore old download behavior. Real media, device, and GPU verification remain separate from stubbed tests.

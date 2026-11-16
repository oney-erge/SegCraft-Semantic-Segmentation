from pathlib import Path

import pytest

from segcraft.training import _checkpoint_payload, _save_checkpoint


class _State:
    def state_dict(self):
        return {"value": 1}


class _Config:
    def to_dict(self):
        return {"runtime": {}}


def test_checkpoint_records_early_stopping_control_state():
    payload = _checkpoint_payload(
        model=_State(), optimizer=_State(), scheduler=None, scaler=None, config=_Config(),
        epoch=4, score=0.4, best_score=0.8, history=[], stale_epochs=3,
    )
    assert payload["checkpoint_version"] == 2
    assert payload["stale_epochs"] == 3


def test_failed_checkpoint_write_preserves_last_usable_file(tmp_path):
    destination = tmp_path / "last.pt"
    destination.write_bytes(b"old checkpoint")

    class FailingTorch:
        @staticmethod
        def save(_payload, path):
            Path(path).write_bytes(b"incomplete")
            raise OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        _save_checkpoint({"epoch": 2}, destination, FailingTorch())
    assert destination.read_bytes() == b"old checkpoint"
    assert list(tmp_path.iterdir()) == [destination]

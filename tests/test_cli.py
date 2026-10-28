import sys

import pytest

import segcraft
from segcraft.cli.main import build_parser, main, resolve_config_path
from segcraft.config.loader import list_available_presets, load_and_validate_config


def test_cli_default_config_works_outside_source_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with resolve_config_path() as config_path:
        assert config_path.name == "base.yaml"
        assert config_path.exists()


def test_packaged_preset_name_loads_outside_source_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with resolve_config_path() as config_path:
        config = load_and_validate_config(config_path, preset_path="pascal_video")

    assert config["data"]["image_size"] == [360, 640]
    assert "pascal_video" in list_available_presets()


def test_public_api_loads_packaged_base_outside_source_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = segcraft.load_config(preset_path="pascal_video")
    assert config["data"]["image_size"] == [360, 640]
    assert segcraft.load_config_object(preset_path="pascal_video").data.image_size == (360, 640)


def test_explicit_missing_local_config_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="missing.yaml"):
        segcraft.load_config(local_path="missing.yaml")
    monkeypatch.setattr(sys, "argv", ["segcraft", "validate", "--local", "missing.yaml"])
    with pytest.raises(FileNotFoundError, match="missing.yaml"):
        main()


def test_cli_optional_default_and_existing_local_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["segcraft", "validate", "--print-config"])
    main()
    assert "SegCraft config is valid." in capsys.readouterr().out
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "local.yaml").write_text("runtime:\n  device: cpu\n")
    main()
    assert '"device": "cpu"' in capsys.readouterr().out


def test_packaged_video_presets_include_fast_and_quality_options(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    names = set(list_available_presets())

    assert "pascal_fast_video" in names
    assert "pascal_quality_video" in names
    assert "cityscapes_quality_video" in names
    assert "ade20k_quality_video" in names


def test_packaged_quality_presets_load_outside_source_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with resolve_config_path() as config_path:
        pascal = load_and_validate_config(config_path, preset_path="pascal_quality_video")
        cityscapes = load_and_validate_config(config_path, preset_path="cityscapes_quality_video")

    assert pascal["model"]["name"] == "deeplabv3_resnet101"
    assert pascal["data"]["image_size"] == [512, 896]
    assert cityscapes["model"]["name"] == "nvidia/segformer-b2-finetuned-cityscapes-1024-1024"
    assert cityscapes["task"]["num_classes"] == 19


def test_cli_accepts_doctor_mode():
    args = build_parser().parse_args(["doctor"])

    assert args.mode == "doctor"


def test_cli_version_flag_reports_the_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"segcraft {segcraft.__version__}"

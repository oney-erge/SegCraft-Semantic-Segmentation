import pytest

from scripts.release_notes import release_notes


def test_release_notes_use_only_requested_changelog_section():
    changelog = "# Changelog\n\n## [1.2.3] - 2026-01-01\n\n### Fixed\n- Works.\n\n## [1.2.2]\n\n- Old.\n"
    notes = release_notes(changelog, "v1.2.3")
    assert 'pip install "segcraft[web]"' in notes
    assert "- Works." in notes
    assert "- Old." not in notes


def test_release_notes_reject_missing_empty_and_invalid_versions():
    with pytest.raises(ValueError, match="no section"):
        release_notes("## [1.2.3]\n- One fix\n", "1.2.4")
    with pytest.raises(ValueError, match="empty section"):
        release_notes("## [1.2.3]\n\n## [1.2.2]\n- Old\n", "1.2.3")
    with pytest.raises(ValueError, match="package version"):
        release_notes("", "../../invalid")

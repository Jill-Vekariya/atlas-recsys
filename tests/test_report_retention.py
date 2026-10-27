import pytest

from atlas.pipeline import train
from atlas.reports import write_new_report


def test_training_rejects_existing_evidence_before_loading_data(tmp_path, monkeypatch):
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    original = report_dir / "validation.json"
    original.write_bytes(b'{"historical": true}\n')

    def unexpected_load(cfg):
        pytest.fail("Existing evidence must be rejected before loading or training")

    monkeypatch.setattr("atlas.pipeline.read_prepared", unexpected_load)
    bundle = tmp_path / "bundle"
    with pytest.raises(ValueError, match="Reports already exist"):
        train({"report_dir": str(report_dir), "bundle_dir": str(bundle)})
    assert original.read_bytes() == b'{"historical": true}\n'
    assert not bundle.exists()


def test_report_writer_preserves_existing_bytes(tmp_path):
    report = tmp_path / "report.json"
    write_new_report(report, {"trial": 1})
    original = report.read_bytes()
    with pytest.raises(FileExistsError):
        write_new_report(report, {"trial": 2})
    assert report.read_bytes() == original

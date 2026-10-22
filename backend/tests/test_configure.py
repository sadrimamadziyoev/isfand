import importlib.util
import json
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location(
    "configure", Path(__file__).resolve().parents[2] / "ops" / "configure.py"
)
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


def test_detects_macos_bundle_without_linux_path(monkeypatch):
    monkeypatch.delenv("BUILD_CA_CERT", raising=False)
    monkeypatch.setattr(
        configure.ssl, "get_default_verify_paths", lambda: SimpleNamespace(cafile=None)
    )
    monkeypatch.setattr(Path, "is_file", lambda path: str(path) == "/etc/ssl/cert.pem")
    assert str(configure.build_ca_path()) == "/etc/ssl/cert.pem"


def test_explicit_ca_is_saved_and_env_is_private(tmp_path, monkeypatch):
    bundle = tmp_path / "trusted bundle.pem"
    bundle.write_text("test bundle")
    monkeypatch.setenv("BUILD_CA_CERT", str(bundle))
    configure.configure(tmp_path)
    env = tmp_path / ".env"
    line = next(
        line
        for line in env.read_text().splitlines()
        if line.startswith("BUILD_CA_CERT=")
    )
    assert json.loads(line.partition("=")[2]) == str(bundle)
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    original = env.read_bytes()
    with pytest.raises(SystemExit, match=".env exists"):
        configure.configure(tmp_path)
    assert env.read_bytes() == original


def test_missing_explicit_ca_does_not_create_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("BUILD_CA_CERT", str(tmp_path / "missing.pem"))
    with pytest.raises(SystemExit, match="No CA bundle found"):
        configure.configure(tmp_path)
    assert not (tmp_path / ".env").exists()

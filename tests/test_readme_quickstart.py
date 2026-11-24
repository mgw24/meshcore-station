"""README fresh-install commands should match the shipped scripts and avoid secrets."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
INSTALL = (ROOT / "scripts/install.sh").read_text(encoding="utf-8")
START = (ROOT / "scripts/start.sh").read_text(encoding="utf-8")
CONFIG = (ROOT / "scripts/configure.sh").read_text(encoding="utf-8")
COMPOSE = (ROOT / "compose.yaml").read_text(encoding="utf-8")
ENV = (ROOT / ".env.example").read_text(encoding="utf-8")


def test_quick_start_is_near_top_after_ai_disclosure():
    assert "## AI Development Disclosure" in README
    assert "## Quick start — fresh installation" in README
    assert README.index("## AI Development Disclosure") < README.index("## Quick start — fresh installation") < README.index("## Features and capabilities")


def test_installation_commands_match_scripts():
    for command in ("git clone https://github.com/mgw24/meshcore-station.git /opt/meshcore-station",
                    "sudo ./scripts/install.sh", "sudo ./scripts/start.sh",
                    "sudo docker compose ps"):
        assert command in README
    assert "Ubuntu Server 24.04 LTS" in README
    assert "24.04" in INSTALL
    assert "sudo ./scripts/start.sh" in INSTALL
    assert "docker compose up -d --build db api collector digest grafana prometheus" in START


def test_ports_serial_and_secrets():
    for expected in ("8088", "3300", "/dev/ttyACM0", "GRAFANA_PUBLIC_URL", "COOKIE_SECURE",
                     "USB Companion", "backup", "docker compose down -v"):
        assert expected in README
    assert "'APP_PORT':'8088'" in CONFIG
    assert "'GRAFANA_PORT':'3300'" in CONFIG
    assert "RADIO_DEVICE=/dev/ttyACM0" in ENV
    assert "${BIND_IP}:${APP_PORT:-8088}:8000" in COMPOSE
    assert "${BIND_IP}:${GRAFANA_PORT:-3300}:3000" in COMPOSE
    assert "Never commit" in README or "Never commit" in ENV
    assert "## AI Development Disclosure" in README


def test_fresh_install_and_upgrade_paths_are_separate():
    assert "### Updating an existing installation" in README
    assert "sudo ./scripts/backup.sh" in README
    assert "git status --short" in README
    assert "QUICKSTART.md" in README

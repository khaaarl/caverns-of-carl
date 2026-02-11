#!/usr/bin/env python3
"""Package Caverns of Carl as a single-file executable using PyInstaller.

Cross-platform script that detects the current OS and architecture to name the
output appropriately.

Steps:
  1. Validate Python venv exists
  2. Ensure PyInstaller is installed (auto-installs if missing)
  3. Run PyInstaller with --onefile, bundling reference_info/ data
  4. Verify output exists, report file size

Output naming (without --version):
  caverns-of-carl-linux-x86_64
  caverns-of-carl-mac-arm64
  caverns-of-carl-windows-x86_64.exe

Output naming (with --version v20260211-143025):
  caverns-of-carl-v20260211-143025-linux-x86_64
  caverns-of-carl-v20260211-143025-mac-arm64
  caverns-of-carl-v20260211-143025-windows-x86_64.exe

Usage:
  python scripts/package_executable.py
  python scripts/package_executable.py --version v20260211-143025

Exit codes:
  0 = packaging succeeded
  1 = any step failed
"""

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

IS_WINDOWS = platform.system() == "Windows"
VENV_PYTHON = (
    REPO_ROOT / "venv" / "Scripts" / "python.exe"
    if IS_WINDOWS
    else REPO_ROOT / "venv" / "bin" / "python"
)


def _normalize_arch(machine: str) -> str:
    """Normalize platform.machine() to a consistent architecture name."""
    m = machine.lower()
    if m in ("x86_64", "amd64"):
        return "x86_64"
    if m in ("arm64", "aarch64"):
        return "arm64"
    return m


def _os_name() -> str:
    s = platform.system()
    if s == "Linux":
        return "linux"
    if s == "Darwin":
        return "mac"
    if s == "Windows":
        return "windows"
    return s.lower()


def executable_name(version: str | None = None) -> str:
    """Build the output executable name for this platform.

    If *version* is given (e.g. "v20260211-143025"), the name becomes
    ``caverns-of-carl-v20260211-143025-linux-x86_64``.  Without a version it
    stays ``caverns-of-carl-linux-x86_64`` for backward-compatibility.
    """
    parts = ["caverns-of-carl"]
    if version:
        parts.append(version)
    parts.append(f"{_os_name()}-{_normalize_arch(platform.machine())}")
    name = "-".join(parts)
    if IS_WINDOWS:
        name += ".exe"
    return name


class Logger:
    def info(self, msg: str) -> None:
        print(f"\u2713 {msg}", file=sys.stderr)

    def step(self, msg: str) -> None:
        print(file=sys.stderr)
        print("\u2501" * 47, file=sys.stderr)
        print(f"  {msg}", file=sys.stderr)
        print("\u2501" * 47, file=sys.stderr)

    def error(self, msg: str) -> None:
        print(file=sys.stderr)
        print(f"\u2717 ERROR: {msg}", file=sys.stderr)
        print(file=sys.stderr)


log = Logger()


def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    defaults: dict[str, Any] = {"check": True}
    defaults.update(kwargs)
    return subprocess.run(args, **defaults)


def check_venv() -> bool:
    log.step("Checking Python virtual environment")

    if not VENV_PYTHON.exists():
        log.error(f"Python venv not found at {VENV_PYTHON}")
        log.error(f"Run: cd {REPO_ROOT} && python3 -m venv venv")
        return False

    log.info(f"Python venv found: {VENV_PYTHON}")
    return True


def ensure_pyinstaller() -> bool:
    log.step("Checking PyInstaller")

    try:
        run(
            [str(VENV_PYTHON), "-c", "import PyInstaller"],
            capture_output=True,
        )
        log.info("PyInstaller already installed")
        return True
    except subprocess.CalledProcessError:
        pass

    log.info("PyInstaller not found, installing...")
    try:
        run([str(VENV_PYTHON), "-m", "pip", "install", "pyinstaller"])
    except subprocess.CalledProcessError:
        log.error("Failed to install PyInstaller")
        return False

    log.info("PyInstaller installed successfully")
    return True


def run_pyinstaller(name: str) -> bool:
    log.step("Running PyInstaller")

    pyinstaller_name = name.removesuffix(".exe")

    # Path separator for --add-data is ; on Windows, : on Unix
    sep = ";" if IS_WINDOWS else ":"

    cmd = [
        str(VENV_PYTHON),
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        pyinstaller_name,
        # Add reference_info/ data directory into the bundle
        "--add-data",
        f"{REPO_ROOT / 'reference_info'}{sep}reference_info",
        # Ensure PyInstaller can find the lib package
        "--paths",
        str(REPO_ROOT),
        # Hidden imports that PyInstaller may not trace automatically
        "--hidden-import",
        "PIL._tkinter_finder",
        "--collect-submodules",
        "lib",
        # Output directories
        "--distpath",
        str(REPO_ROOT / "dist"),
        "--workpath",
        str(REPO_ROOT / "build" / "pyinstaller"),
        "--specpath",
        str(REPO_ROOT / "build" / "pyinstaller"),
    ]

    # --strip is only available on Unix
    if not IS_WINDOWS:
        cmd.append("--strip")

    cmd.append(str(REPO_ROOT / "caverns_of_carl.py"))

    try:
        run(cmd, cwd=str(REPO_ROOT))
    except subprocess.CalledProcessError:
        log.error("PyInstaller failed")
        return False

    log.info("PyInstaller completed")
    return True


def verify_output(name: str) -> bool:
    log.step("Verifying output")

    output = REPO_ROOT / "dist" / name

    if not output.exists():
        log.error(f"Expected output not found: {output}")
        return False

    size_bytes = output.stat().st_size
    if size_bytes >= 1024 * 1024:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        size_str = f"{size_bytes / 1024:.1f} KB"

    log.info(f"Output: {output}")
    log.info(f"Size: {size_str}")

    # On Unix, verify it's executable
    if not IS_WINDOWS and not os.access(output, os.X_OK):
        log.error("Output exists but is not executable")
        return False

    log.info("Executable verified")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package Caverns of Carl as a single-file executable"
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Version tag to embed in the executable name (e.g. v20260211-143025)",
    )
    args = parser.parse_args()

    name = executable_name(args.version)
    log.step(f"Packaging Caverns of Carl: {name}")
    log.info(f"repo_root: {REPO_ROOT}")

    if not check_venv():
        return 1

    if not ensure_pyinstaller():
        return 1

    if not run_pyinstaller(name):
        return 1

    if not verify_output(name):
        return 1

    log.step("\u2713 Packaging complete!")
    log.info(f"Run: {REPO_ROOT / 'dist' / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

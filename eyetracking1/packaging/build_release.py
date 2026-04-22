from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app_meta import APP_NAME, APP_PUBLISHER, APP_VERSION  # noqa: E402


DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
RELEASE_DIR = PROJECT_ROOT / "release"
SPEC_PATH = PROJECT_ROOT / "packaging" / "gazespeak.spec"
INNO_SCRIPT = PROJECT_ROOT / "packaging" / "windows" / "gazespeak.iss"


def run(command: list[str], cwd: Path = PROJECT_ROOT) -> None:
    print("+", " ".join(str(part) for part in command))
    subprocess.run(command, cwd=str(cwd), check=True)


def build_pyinstaller(clean: bool) -> None:
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm"]
    if clean:
        command.append("--clean")
    command.append(str(SPEC_PATH))
    run(command)


def smoke_test_command() -> list[str]:
    if sys.platform == "darwin":
        return [str(DIST_DIR / f"{APP_NAME}.app" / "Contents" / "MacOS" / APP_NAME), "--self-check"]
    if sys.platform.startswith("win"):
        return [str(DIST_DIR / APP_NAME / f"{APP_NAME}.exe"), "--self-check"]
    return [str(DIST_DIR / APP_NAME / APP_NAME), "--self-check"]


def run_smoke_test() -> None:
    run(smoke_test_command())


def find_windeployqt() -> Path | None:
    if not sys.platform.startswith("win"):
        return None
    try:
        from PySide6.QtCore import QLibraryInfo

        qt_bin = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.LibraryExecutablesPath))
        candidate = qt_bin / "windeployqt.exe"
        if candidate.exists():
            return candidate
    except Exception:
        pass

    for candidate in [
        Path(sys.executable).resolve().parent / "windeployqt.exe",
        Path(r"C:\Program Files\Qt\bin\windeployqt.exe"),
        Path(r"C:\Qt\bin\windeployqt.exe"),
    ]:
        if candidate.exists():
            return candidate
    return None


def run_windeployqt() -> None:
    tool = find_windeployqt()
    if tool is None:
        print("WARN: windeployqt topilmadi, PyInstaller hooklariga tayaniladi.")
        return
    executable = DIST_DIR / APP_NAME / f"{APP_NAME}.exe"
    run([str(tool), "--no-translations", str(executable)])


def sign_macos_app(app_path: Path) -> None:
    identity = os.getenv("APPLE_SIGN_IDENTITY", "").strip()
    if not identity:
        print("WARN: APPLE_SIGN_IDENTITY berilmagan, macOS build unsigned bo'ladi.")
        return
    run(["codesign", "--force", "--deep", "--options", "runtime", "--sign", identity, str(app_path)])


def notarize_macos_artifact(dmg_path: Path) -> None:
    profile = os.getenv("APPLE_NOTARY_PROFILE", "").strip()
    if not profile:
        return
    run(["xcrun", "notarytool", "submit", str(dmg_path), "--keychain-profile", profile, "--wait"])
    run(["xcrun", "stapler", "staple", str(dmg_path)])


def build_macos_dmg() -> Path:
    app_path = DIST_DIR / f"{APP_NAME}.app"
    sign_macos_app(app_path)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    dmg_path = RELEASE_DIR / f"GazeSpeak-{APP_VERSION}-macOS.dmg"
    if dmg_path.exists():
        dmg_path.unlink()
    run(
        [
            "hdiutil",
            "create",
            "-volname",
            APP_NAME,
            "-srcfolder",
            str(app_path),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ]
    )
    notarize_macos_artifact(dmg_path)
    return dmg_path


def find_iscc() -> Path | None:
    env_path = os.getenv("ISCC_PATH", "").strip()
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate

    local_appdata = os.getenv("LOCALAPPDATA", "").strip()
    if local_appdata:
        candidate = Path(local_appdata) / "Programs" / "Inno Setup 6" / "ISCC.exe"
        if candidate.exists():
            return candidate

    for candidate in [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]:
        if candidate.exists():
            return candidate
    return None


def _try_install_inno_setup() -> Path | None:
    if not sys.platform.startswith("win"):
        return None

    winget = shutil.which("winget")
    if winget:
        try:
            run(
                [
                    winget,
                    "install",
                    "-e",
                    "--id",
                    "JRSoftware.InnoSetup",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                    "--silent",
                ]
            )
        except subprocess.CalledProcessError:
            pass
        else:
            candidate = find_iscc()
            if candidate is not None:
                return candidate

    choco = shutil.which("choco")
    if choco:
        try:
            run([choco, "install", "innosetup", "--no-progress", "-y"])
        except subprocess.CalledProcessError:
            return None
        return find_iscc()

    return None


def build_windows_installer() -> Path:
    iscc = find_iscc()
    if iscc is None:
        print("WARN: ISCC.exe topilmadi. Inno Setup avtomatik o'rnatishga urinilmoqda.")
        iscc = _try_install_inno_setup()
    if iscc is None:
        raise RuntimeError("ISCC.exe topilmadi. Inno Setup 6 o'rnating yoki ISCC_PATH belgilang.")

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    dist_app_dir = DIST_DIR / APP_NAME
    run(
        [
            str(iscc),
            f"/DMyAppVersion={APP_VERSION}",
            f"/DMyAppPublisher={APP_PUBLISHER}",
            f"/DMyDistDir={dist_app_dir}",
            f"/DMyOutputDir={RELEASE_DIR}",
            str(INNO_SCRIPT),
        ]
    )
    return RELEASE_DIR / f"GazeSpeak-{APP_VERSION}-Windows-Setup.exe"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build release artifacts for GazeSpeak Desktop.")
    parser.add_argument(
        "--target",
        choices=["auto", "macos", "windows"],
        default="auto",
        help="Installer target. Default uses the current platform.",
    )
    parser.add_argument("--clean", action="store_true", help="Delete build/dist/release before building.")
    parser.add_argument("--skip-installer", action="store_true", help="Only build the PyInstaller app bundle.")
    return parser.parse_args()


def clean_outputs() -> None:
    for path in (BUILD_DIR, DIST_DIR, RELEASE_DIR):
        if path.exists():
            shutil.rmtree(path)


def main() -> int:
    args = parse_args()
    target = args.target
    if target == "auto":
        target = "windows" if sys.platform.startswith("win") else "macos" if sys.platform == "darwin" else "auto"

    if args.clean:
        clean_outputs()

    build_pyinstaller(clean=args.clean)
    if sys.platform.startswith("win"):
        run_windeployqt()
    run_smoke_test()

    if args.skip_installer:
        print("PyInstaller build va smoke test tugadi.")
        return 0

    if target == "windows":
        artifact = build_windows_installer()
    elif target == "macos":
        artifact = build_macos_dmg()
    else:
        print("Installer target bu platforma uchun yozilmagan. PyInstaller build tayyor.")
        return 0

    print(f"Release artifact: {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

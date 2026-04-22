# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

project_dir = Path(SPECPATH).parent
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

from app_meta import APP_DESCRIPTION, APP_ID, APP_NAME, APP_VERSION

datas = [
    (str(project_dir / "models" / "face_landmarker.task"), "models"),
]
binaries = []
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

for package_name in ("mediapipe", "edge_tts", "pyttsx3"):
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package_name)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hiddenimports
    except Exception:
        pass

try:
    datas += collect_data_files("cv2")
except Exception:
    pass

for distribution_name in ("mediapipe", "edge-tts", "pyttsx3"):
    try:
        datas += copy_metadata(distribution_name)
    except Exception:
        pass

a = Analysis(
    [str(project_dir / "desktop_app.py")],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_dir / "packaging" / "runtime_hook.py")],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        bundle_identifier=APP_ID,
        info_plist={
            "CFBundleDisplayName": APP_NAME,
            "CFBundleName": APP_NAME,
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "CFBundleIdentifier": APP_ID,
            "NSCameraUsageDescription": "GazeSpeak eye tracking needs camera access.",
            "NSHighResolutionCapable": "True",
            "LSApplicationCategoryType": "public.app-category.medical",
            "CFBundleGetInfoString": APP_DESCRIPTION,
        },
    )

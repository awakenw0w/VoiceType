# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


hiddenimports = []
for package in (
    "faster_whisper",
    "ctranslate2",
    "av",
    "huggingface_hub",
    "tokenizers",
    "openai",
    "pydantic",
    "pydantic_core",
    "httpx",
    "httpcore",
    "anyio",
    "sniffio",
):
    hiddenimports += collect_submodules(package)

datas = []
for package in ("faster_whisper",):
    datas += collect_data_files(package)


a = Analysis(
    ["src/win_whisper_dictation_launcher.py"],
    pathex=["src"],
    binaries=[],
    datas=datas + [("config.toml", ".")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VoiceType",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VoiceType",
)

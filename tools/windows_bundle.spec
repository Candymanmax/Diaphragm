from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs, copy_metadata


root = Path(SPECPATH).resolve().parent
assets = root / "harness_ui" / "assets"
datas = [
    (str(root / "config.default.yaml"), "."),
    (str(assets / "icons"), "harness_ui/assets/icons"),
    (str(assets / "diaphragm_icon.ico"), "harness_ui/assets"),
    (str(assets / "diaphragm_icon.svg"), "harness_ui/assets"),
]
binaries = collect_dynamic_libs("sklearn")
hiddenimports = []
for package in ("chatterbox", "syntok"):
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports

datas += collect_data_files("perth")
for package in ("diffusers", "transformers"):
    datas += copy_metadata(package, recursive=True)

desktop_script = root / "desktop_gui.py"
console_script = root / "diaphragm.py"
analysis = Analysis(
    [str(desktop_script), str(console_script)],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["torch", "torchaudio"],
    # Numba and Transformers inspect source files while loading speech models.
    module_collection_mode={"librosa": "py", "transformers": "py"},
)
pyz = PYZ(analysis.pure)


def make_executable(name, console, other_script):
    scripts = [entry for entry in analysis.scripts if Path(entry[1]) != other_script]
    return EXE(
        pyz,
        scripts,
        exclude_binaries=True,
        name=name,
        console=console,
        icon=str(assets / "diaphragm_icon.ico"),
    )


desktop = make_executable("Diaphragm", False, console_script)
cli = make_executable("diaphragm-cli", True, desktop_script)
bundle = COLLECT(desktop, cli, analysis.binaries, analysis.datas, name="Diaphragm")

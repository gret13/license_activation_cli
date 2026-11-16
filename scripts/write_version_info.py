import tomllib
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    with (project_root / "pyproject.toml").open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    parts = tuple(int(part) for part in version.split("."))
    if len(parts) != 4 or any(part < 0 or part > 65535 for part in parts):
        raise ValueError("Expected four integers between 0 and 65535")
    target = project_root / "build" / "version_info.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "VSVersionInfo(ffi=FixedFileInfo(filevers=" + str(parts) + ", prodvers=" + str(parts)
        + ", mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)), "
        "kids=[StringFileInfo([StringTable('040904B0', ["
        f"StringStruct('FileVersion', '{version}'), "
        f"StringStruct('ProductVersion', '{version}'), "
        "StringStruct('FileDescription', 'License Activation CLI'), "
        "StringStruct('ProductName', 'License Activation CLI')"
        "])]) , VarFileInfo([VarStruct('Translation', [1033, 1200])])])\n",
        encoding="utf-8",
    )
    print(target)


if __name__ == "__main__":
    main()

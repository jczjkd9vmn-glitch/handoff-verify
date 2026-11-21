"""Verify a copied directory or ZIP against its source by path, type, and SHA-256."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile
import zlib


def direct_path(path: Path) -> Path:
    path = path.expanduser()
    if path.is_symlink() or path.is_junction():
        raise OSError(f"Expected a direct path: {path}")
    return path.resolve(strict=True)


def scan(root: Path) -> dict[str, str | None]:
    entries: dict[str, str | None] = {}
    pending = [root]
    while pending:
        with os.scandir(pending.pop()) as children:
            for child in children:
                path = Path(child.path)
                name = path.relative_to(root).as_posix()
                info = child.stat(follow_symlinks=False)
                is_junction = (
                    getattr(info, "st_reparse_tag", 0) == stat.IO_REPARSE_TAG_MOUNT_POINT
                )
                if stat.S_ISDIR(info.st_mode) and not is_junction:
                    entries[name] = None
                    pending.append(path)
                elif stat.S_ISREG(info.st_mode):
                    with path.open("rb") as stream:
                        digest = hashlib.file_digest(stream, "sha256").hexdigest()
                        after = os.fstat(stream.fileno())
                    if (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise OSError(f"File changed during verification: {path}")
                    entries[name] = digest
                else:
                    raise OSError(f"Unsupported entry (link or special file): {path}")
    return entries


def scan_zip(path: Path) -> dict[str, str | None]:
    entries: dict[str, str | None] = {}
    explicit = set()
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            name = member.orig_filename.removesuffix("/")
            parts = name.split("/")
            if any(part in {"", ".", ".."} for part in parts) or any(
                character in name for character in ("\\", ":", "\x00")
            ):
                raise OSError(f"Invalid ZIP member path: {name!r}")
            if name in explicit:
                raise OSError(f"Duplicate ZIP member: {name!r}")
            explicit.add(name)

            kind = stat.S_IFDIR if member.is_dir() else stat.S_IFREG
            if member.create_system == 3:
                mode = stat.S_IFMT(member.external_attr >> 16)
                if mode not in {0, kind}:
                    raise OSError(f"Unsupported ZIP member type: {name!r}")

            for parent in PurePosixPath(name).parents:
                if parent != PurePosixPath(".") and entries.setdefault(parent.as_posix(), None) is not None:
                    raise OSError(f"ZIP path is both a file and a directory: {parent.as_posix()!r}")
            if member.is_dir():
                entries[name] = None
            else:
                if name in entries:
                    raise OSError(f"ZIP path is both a file and a directory: {name!r}")
                with archive.open(member) as stream:
                    entries[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return entries


def compare(source: Path, copy: Path) -> list[dict[str, str]]:
    source, copy = direct_path(source), direct_path(copy)
    if not source.is_dir():
        raise NotADirectoryError(str(source))
    if source.samefile(copy) or source in copy.parents or copy in source.parents:
        raise OSError("Choose separate paths outside each other's directory trees")
    if not (copy.is_dir() or copy.is_file()):
        raise OSError(f"Expected a directory or ZIP file: {copy}")

    # shortcut: These are live directory reads. Use snapshots if a writer can change either tree.
    originals = scan(source)
    copies = scan(copy) if copy.is_dir() else scan_zip(copy)
    differences = []
    for name in sorted(originals.keys() | copies.keys()):
        if name not in copies:
            category = "missing"
        elif name not in originals:
            category = "extra"
        elif originals[name] == copies[name]:
            continue
        elif originals[name] is None or copies[name] is None:
            category = "type"
        else:
            category = "content"
        differences.append({"path": name, "kind": category})
    return differences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="original directory")
    parser.add_argument("copy", type=Path, help="directory or ZIP to verify")
    parser.add_argument("--json", action="store_true", help="report verification results as JSON")
    args = parser.parse_args()

    try:
        differences = compare(args.source, args.copy)
    except (OSError, RuntimeError, zipfile.BadZipFile, zlib.error) as error:
        if args.json:
            print(json.dumps({"status": "error", "error": str(error)}))
        else:
            print(f"Could not verify: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"status": "different" if differences else "match", "differences": differences}))
    elif differences:
        for difference in differences:
            print(f"{difference['kind']}: {difference['path']!r}")
    else:
        print("Directory trees match.")
    return int(bool(differences))


if __name__ == "__main__":
    raise SystemExit(main())

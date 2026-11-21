"""Compare two directory trees by path, entry type, and SHA-256."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys


def directory(path: Path) -> Path:
    path = path.expanduser()
    if path.is_symlink() or path.is_junction():
        raise OSError(f"Expected a direct directory path: {path}")
    path = path.resolve(strict=True)
    if not path.is_dir():
        raise NotADirectoryError(str(path))
    return path


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


def compare(source: Path, copy: Path) -> list[dict[str, str]]:
    source, copy = directory(source), directory(copy)
    if source.samefile(copy) or source in copy.parents or copy in source.parents:
        raise OSError("Choose two separate, non-overlapping directories")

    # shortcut: These are live directory reads. Use snapshots if a writer can change either tree.
    originals, copies = scan(source), scan(copy)
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
    parser.add_argument("copy", type=Path, help="directory to verify")
    parser.add_argument("--json", action="store_true", help="report verification results as JSON")
    args = parser.parse_args()

    try:
        differences = compare(args.source, args.copy)
    except OSError as error:
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

# Handoff Verify

Verify that a staged release, extracted ZIP, or copied folder contains the same files and directories as its source. Handoff Verify reports missing or extra entries, file/directory conflicts, and changed file bytes, including changes that leave file sizes unchanged.

## Quick start

Requires Python 3.12 or newer. Download or clone the project and run the script from its directory. There are no dependencies to install.

```powershell
py -3 handoff_verify.py "C:\Release Staging" "D:\Delivered Build"
```

For a CI step on systems with `python3` on `PATH`:

```sh
python3 handoff_verify.py ./dist/staging ./dist/unpacked --json
```

The command reads both directories and prints its results. Use its exit status to allow or stop the next step in a release pipeline.

| Exit status | Meaning |
| --- | --- |
| `0` | Paths, types, and file contents match. |
| `1` | At least one difference was found. |
| `2` | Verification could not finish, or the arguments were invalid. |

Verification results with `--json` are a single object on standard output. Difference paths are relative to the two roots, use `/` separators, and are sorted by path.

```json
{"status":"different","differences":[{"path":"guide.pdf","kind":"content"}]}
```

The other result statuses are `match`, with an empty `differences` list, and `error`, with an `error` message. Difference kinds are `missing`, `extra`, `type`, and `content`.

## What it verifies

The comparison covers exact relative filenames, directory entries (including empty directories), and SHA-256 hashes of regular files. Timestamps, ownership, permissions, and extended attributes are outside its scope. Symbolic links, junctions, and special files inside either tree stop verification with an error. Compare stable trees or filesystem snapshots for a point-in-time result.

## Contributing

File an issue with a minimal directory layout, your OS and Python version, and the result you expected. Use sample filenames and data that you can share publicly. GitHub Actions runs the end-to-end tests on Windows and Linux. To run them locally:

```sh
python -B -m unittest -v
```

Licensed under the [MIT License](LICENSE).

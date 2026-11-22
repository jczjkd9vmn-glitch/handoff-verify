# Handoff Verify

Compare a staged release with the ZIP users will download, or compare an original folder with its copy. Handoff Verify reports missing or extra entries, file/directory conflicts, and changed file bytes, including changes that leave file sizes unchanged. It reads ZIP contents directly.

## Quick start

Requires Python 3.12 or newer. Download or clone the project and run the script from its directory. There are no dependencies to install.

```powershell
py -3 handoff_verify.py "C:\Release Staging" "D:\Delivered Build"
```

Run this CI check after packaging and before publishing. Keep the ZIP outside the staging folder and use that folder's contents as the ZIP root:

```sh
python3 handoff_verify.py ./dist/staging ./dist/release.zip --json
```

Use its exit status to allow or stop the next step in a release pipeline. For example, GitHub's artifact upload action skips dot-prefixed paths by default. If the staging directory contains a required `site/.export/index.html` and packaging omits it, the check reports both missing entries. The tests reproduce that shape with a local ZIP. [See the reported omission.](https://github.com/actions/upload-artifact/issues/614)

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

The comparison covers exact relative filenames, directory entries (including empty directories), and SHA-256 hashes of regular files. ZIP parent folders can be explicit entries or inferred from their contents. Timestamps, ownership, permissions, and extended attributes are outside its scope. Symbolic links, junctions, special files, and ambiguous ZIP paths stop verification with an error. Compare stable inputs or filesystem snapshots for a point-in-time result.

## Contributing

If your project ships a ZIP, you can [try Handoff Verify on one real release and share feedback](https://github.com/jczjkd9vmn-glitch/handoff-verify/issues/1).

File an issue with a minimal directory layout, your OS and Python version, and the result you expected. Use sample filenames and data that you can share publicly. GitHub Actions runs the end-to-end tests on Windows and Linux. To run them locally:

```sh
python -B -m unittest -v
```

Licensed under the [MIT License](LICENSE).

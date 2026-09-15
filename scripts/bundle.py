import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from scripts.artifacts import ROOT, code_files


def build_bundle(target: Path, root: Path = ROOT) -> dict:
    paths = code_files(root)
    manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.writestr(str(path.relative_to(root)), path.read_bytes())
        archive.writestr("bundle-manifest.json", json.dumps(manifest, indent=2))
    return {
        "path": str(target),
        "files": len(paths),
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/runpod-source.zip"))
    args = parser.parse_args()
    print(json.dumps(build_bundle(args.output), indent=2))


if __name__ == "__main__":
    main()

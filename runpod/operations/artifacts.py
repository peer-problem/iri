import hashlib
import json
from pathlib import Path

from runpod.settings import REPO_ROOT as ROOT


def code_files(root: Path = ROOT) -> list[Path]:
    """Explicit allowlist: never include env files, raw data, caches or agent docs."""
    paths = [
        root / name
        for name in (
            "README.md",
            "runpod/operations/init_local.py",
            "api/__init__.py",
            "runpod/pyproject.toml",
            "runpod/uv.lock",
            "runpod/.python-version",
            ".gitignore",
            "runpod/requirements-gpu.txt",
            "runpod/requirements-training.txt",
            "runpod/requirements-training.lock",
        )
    ]
    for directory, pattern in (
        ("api/app", "*.py"),
        ("runpod/operations", "*.py"),
        ("runpod", "*.py"),
        ("runpod/tests", "*.py"),
        ("runpod/configs", "*.json"),
        ("api/tests", "*.py"),
        ("api/configs", "*.json"),
        ("runpod/data", "*.json"),
        ("runpod/data", "*.jsonl"),
    ):
        paths.extend((root / directory).glob(pattern))
    return sorted(
        {
            path
            for path in paths
            if path.is_file()
            and not path.is_symlink()
            and path.resolve().is_relative_to(root.resolve())
            and not any(parent.is_symlink() for parent in path.parents if parent != root.parent)
        }
    )


def code_manifest(root: Path = ROOT) -> dict:
    files = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in code_files(root)
    }
    return {
        "files": files,
        "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
    }

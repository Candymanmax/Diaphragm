from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import argparse
import re
import subprocess
import sys


PRIVATE_DIRECTORIES = {
    "audio",
    "chunks",
    "final",
    "input",
    "jobs",
    "logs",
    "models",
    "voices",
}
PRIVATE_FILES = {
    "config.yaml",
    ".env",
}
PRIVATE_SUFFIXES = {
    ".aac",
    ".bin",
    ".ckpt",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".pt",
    ".pth",
    ".safetensors",
    ".wav",
}
CONTENT_PATTERNS = {
    "private-key header": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "Hugging Face token": re.compile(rb"\bhf_[A-Za-z0-9]{20,}\b"),
    "OpenAI-style token": re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(rb"\bgh[opsu]_[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
    "bearer token": re.compile(
        rb"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}",
        re.IGNORECASE,
    ),
    "Windows user path": re.compile(
        rb"\b[A-Za-z]:\\Users\\[^\\\s]+\\",
        re.IGNORECASE,
    ),
    "email address": re.compile(
        rb"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        re.IGNORECASE,
    ),
    "credential-bearing URL": re.compile(
        rb"https?://[^\s/:]+:[^\s/@]+@",
        re.IGNORECASE,
    ),
}


@dataclass(frozen=True)
class PrivacyFinding:
    path: str
    reason: str


def commit_candidates(project_root):
    result = subprocess.run(
        (
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ),
        cwd=project_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [
        value.decode("utf-8", errors="surrogateescape")
        for value in result.stdout.split(b"\0")
        if value
    ]


def _private_path_reason(relative_value):
    relative = PurePosixPath(str(relative_value).replace("\\", "/"))
    lowered_parts = tuple(part.casefold() for part in relative.parts)
    lowered_name = relative.name.casefold()

    if lowered_parts and lowered_parts[0] in PRIVATE_DIRECTORIES:
        return "private directory"

    if lowered_name in PRIVATE_FILES or lowered_name.startswith(".env."):
        if lowered_name != ".env.example":
            return "private file"

    if relative.suffix.casefold() in PRIVATE_SUFFIXES:
        return "audio/model asset"

    if (
        len(relative.parts) == 1
        and relative.suffix.casefold() == ".txt"
        and lowered_name != "requirements.txt"
    ):
        return "root prompt/script"

    return None


def audit_files(project_root, relative_paths):
    project_root = Path(project_root).resolve()
    findings = []

    for relative_value in relative_paths:
        relative = PurePosixPath(str(relative_value).replace("\\", "/"))
        path_reason = _private_path_reason(relative)

        if path_reason:
            findings.append(PrivacyFinding(str(relative), path_reason))
            continue

        candidate = project_root.joinpath(*relative.parts)

        try:
            data = candidate.read_bytes()
        except OSError:
            findings.append(PrivacyFinding(str(relative), "unreadable candidate"))
            continue

        if b"\0" in data[:8192]:
            continue

        for reason, pattern in CONTENT_PATTERNS.items():
            if pattern.search(data):
                findings.append(PrivacyFinding(str(relative), reason))

    return findings


def audit_history(project_root):
    """Inspect every reachable historical blob without printing its content."""
    project_root = Path(project_root).resolve()
    result = subprocess.run(
        ("git", "rev-list", "--objects", "--all"),
        cwd=project_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    findings = set()
    inspected_objects = set()

    for line in result.stdout.splitlines():
        object_and_path = line.split(b" ", 1)

        if len(object_and_path) != 2:
            continue

        object_id = object_and_path[0].decode("ascii")
        path = object_and_path[1].decode(
            "utf-8",
            errors="surrogateescape",
        )
        path_reason = _private_path_reason(path)

        if path_reason:
            findings.add((path, f"historical {path_reason}"))

        if object_id in inspected_objects:
            continue

        inspected_objects.add(object_id)
        object_type = subprocess.run(
            ("git", "cat-file", "-t", object_id),
            cwd=project_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()

        if object_type != b"blob":
            continue

        size = int(subprocess.run(
            ("git", "cat-file", "-s", object_id),
            cwd=project_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip())

        if size > 5 * 1024 * 1024:
            continue

        data = subprocess.run(
            ("git", "cat-file", "blob", object_id),
            cwd=project_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout

        if b"\0" in data[:8192]:
            continue

        for reason, pattern in CONTENT_PATTERNS.items():
            if pattern.search(data):
                findings.add((path, f"historical {reason}"))

    return [
        PrivacyFinding(path, reason)
        for path, reason in sorted(findings)
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Audit current Git candidates and reachable history"
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=str(Path(__file__).resolve().parent),
    )
    parser.add_argument(
        "--current-only",
        action="store_true",
        help="Skip the reachable Git-history audit",
    )
    args = parser.parse_args(argv)
    project_root = Path(args.project_root)

    try:
        candidates = commit_candidates(project_root)
        history_findings = (
            [] if args.current_only else audit_history(project_root)
        )
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"PRIVACY CHECK ERROR: {error}", file=sys.stderr)
        return 2

    findings = audit_files(project_root, candidates) + history_findings

    if findings:
        print("Privacy check failed. Repository items requiring review:")

        for finding in findings:
            print(f"- {finding.path}: {finding.reason}")

        return 1

    print(
        f"Privacy check passed: {len(candidates)} tracked/unignored "
        "commit candidates inspected"
        + ("." if args.current_only else ", including reachable history.")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

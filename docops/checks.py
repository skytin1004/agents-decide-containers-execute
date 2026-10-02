"""Read-only checks over a fixed snapshot. No network or command execution."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from .contracts import WorkRequest

FIXTURE = Path(__file__).parent / "fixture"
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")


def safe_path(root: Path, relative: str) -> Path:
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Path escapes the repository snapshot")
    return path


def check_links(root: Path) -> list[dict]:
    findings = []
    for source in sorted(root.rglob("*.md")):
        if not source.resolve().is_relative_to(root.resolve()):
            raise ValueError("Symlinks cannot escape the repository snapshot")
        fenced = False
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("```", "~~~")):
                fenced = not fenced
                continue
            if fenced:
                continue
            for match in LINK.finditer(line):
                raw = match.group(1)
                target = urlsplit(raw)
                if target.scheme or target.netloc or not target.path:
                    continue
                relative = unquote(target.path)
                # Repository-root links and relative links are both supported.
                candidate = root / relative.lstrip("/") if relative.startswith("/") else source.parent / relative
                candidate = candidate.resolve()
                valid = candidate.is_relative_to(root.resolve()) and candidate.is_file()
                if not valid:
                    findings.append({"file": source.relative_to(root).as_posix(),
                                     "line": line_number, "target": raw, "kind": "broken_internal_link"})
    return findings


def check_translation_drift(root: Path) -> list[dict]:
    manifest = json.loads((root / "translations.json").read_text(encoding="utf-8"))
    findings = []
    for item in manifest["translations"]:
        source = safe_path(root, item["source"])
        translation = safe_path(root, item["translation"])
        # Normalize line endings so Git's CRLF conversion does not create false drift.
        current = hashlib.sha256(source.read_text(encoding="utf-8").encode()).hexdigest()
        if not translation.is_file() or current != item["source_sha256"]:
            findings.append({"file": item["translation"], "source": item["source"],
                             "kind": "source_changed" if translation.is_file() else "translation_missing"})
    return findings


def execute(request: WorkRequest, root: Path = FIXTURE) -> dict:
    handlers = {"check_links": check_links, "check_translation_drift": check_translation_drift}
    results = {action: handlers[action](root) for action in request.actions}
    return {"schema_version": 1, "request_id": request.request_id,
            "repository_id": request.repository_id, "status": "completed",
            "actions": list(request.actions), "findings": results,
            "finding_count": sum(len(items) for items in results.values())}


def markdown_report(result: dict) -> str:
    lines = ["# Documentation maintenance report", "",
             f"Request: `{result['request_id']}`",
             f"Repository: `{result['repository_id']}`",
             f"Status: **{result['status']}**",
             f"Findings: **{result['finding_count']}**", ""]
    for action, findings in result["findings"].items():
        lines += [f"## {action}", ""]
        if not findings:
            lines.append("No findings.")
        for finding in findings:
            if action == "check_links":
                lines.append(f"- `{finding['file']}:{finding['line']}` points to missing `{finding['target']}`.")
            else:
                lines.append(f"- `{finding['file']}` needs review: `{finding['source']}` changed since the recorded translation baseline.")
        lines.append("")
    lines += ["The checks inspect a fixed local snapshot. They do not translate, modify files, or open a pull request.", ""]
    return "\n".join(lines)

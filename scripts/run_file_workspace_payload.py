from __future__ import annotations

import ast
import base64
import binascii
import io
from pathlib import Path, PurePosixPath
import shutil
import tarfile


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_SCRIPT = ROOT / "scripts" / "apply_file_workspace.py"
MAX_MEMBER_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 150 * 1024 * 1024
MAX_MEMBERS = 2_000
BASE64_ALPHABET = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
)


def _safe_relative_path(name: str) -> Path:
    normalized = name.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if not normalized or pure.is_absolute() or ".." in pure.parts:
        raise RuntimeError(f"Unsafe payload path: {name}")
    if pure.parts and ":" in pure.parts[0]:
        raise RuntimeError(f"Unsafe Windows payload path: {name}")
    return Path(*pure.parts)


def _load_payload(path: Path) -> str:
    """Read PAYLOAD without importing or parsing the damaged applicator."""

    source = path.read_text(encoding="utf-8")
    marker = "PAYLOAD ="
    marker_position = source.find(marker)
    if marker_position < 0:
        raise RuntimeError("PAYLOAD is missing")

    literal_start = marker_position + len(marker)
    while literal_start < len(source) and source[literal_start].isspace():
        literal_start += 1
    if literal_start >= len(source) or source[literal_start] not in {'\"', "'"}:
        raise RuntimeError("PAYLOAD must start as a string literal")

    quote = source[literal_start]
    escaped = False
    literal_end: int | None = None
    position = literal_start + 1
    while position < len(source):
        character = source[position]
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == quote:
            literal_end = position
            break
        position += 1

    if literal_end is None:
        # The generated applicator was uploaded without the final quote and
        # executable footer. The base64 body itself is still recoverable.
        value = source[literal_start + 1 :].strip()
    else:
        literal = source[literal_start : literal_end + 1]
        try:
            value = ast.literal_eval(literal)
        except (ValueError, TypeError, SyntaxError) as exc:
            raise RuntimeError("PAYLOAD must be a literal string") from exc

    if not isinstance(value, str) or not value:
        raise RuntimeError("PAYLOAD must be a non-empty string")
    invalid = sorted(set(value) - BASE64_ALPHABET)
    if invalid:
        preview = "".join(invalid[:8])
        raise RuntimeError(f"PAYLOAD contains non-base64 characters: {preview!r}")
    return value


def main() -> int:
    encoded = _load_payload(PAYLOAD_SCRIPT)
    try:
        compressed = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("PAYLOAD is not valid base64") from exc

    total = 0
    with tarfile.open(fileobj=io.BytesIO(compressed), mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) > MAX_MEMBERS:
            raise RuntimeError("PAYLOAD contains too many files")

        validated: list[tuple[tarfile.TarInfo, Path]] = []
        for member in members:
            relative = _safe_relative_path(member.name)
            if member.issym() or member.islnk() or member.isdev():
                raise RuntimeError(f"Unsupported payload member: {member.name}")
            if not (member.isdir() or member.isfile()):
                raise RuntimeError(f"Unsupported payload member type: {member.name}")
            if member.size < 0 or member.size > MAX_MEMBER_BYTES:
                raise RuntimeError(f"Payload member is too large: {member.name}")
            total += member.size
            if total > MAX_TOTAL_BYTES:
                raise RuntimeError("PAYLOAD is too large")
            target = (ROOT / relative).resolve()
            try:
                target.relative_to(ROOT.resolve())
            except ValueError as exc:
                raise RuntimeError(f"Payload path escapes repository: {member.name}") from exc
            validated.append((member, target))

        for member, target in validated:
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            source_file = archive.extractfile(member)
            if source_file is None:
                raise RuntimeError(f"Cannot read payload member: {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.payload-tmp")
            with source_file, temporary.open("wb") as destination:
                shutil.copyfileobj(source_file, destination, length=1024 * 1024)
            temporary.replace(target)

    print(f"Applied {len(validated)} payload members ({total} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

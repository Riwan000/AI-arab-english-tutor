"""Verify Streamlit layer has no direct service/repository imports (issue #54)."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_ROOTS = {"services", "repositories"}


def _imports_in_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in FORBIDDEN_ROOTS:
                found.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_ROOTS:
                    found.append(alias.name)
    return found


def main() -> int:
    targets = [ROOT / "app.py", *sorted((ROOT / "components").glob("*.py"))]
    violations: list[str] = []

    for path in targets:
        bad = _imports_in_file(path)
        for module in bad:
            violations.append(f"{path.relative_to(ROOT)}: imports {module}")

    if violations:
        print("Forbidden imports found:")
        for line in violations:
            print(f"  - {line}")
        return 1

    example = ROOT / ".streamlit" / "secrets.toml.example"
    for line in example.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if "OPENROUTER" in stripped.upper():
            print("secrets.toml.example contains OPENROUTER config (issue #55)")
            return 1

    print("No direct service/repository imports in app.py or components/ (issue #54): OK")
    print("Streamlit secrets example has no OPENROUTER_API_KEY (issue #55): OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

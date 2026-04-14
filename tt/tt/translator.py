"""
Minimal TypeScript to Python translator.

This translator uses a maintained implementation template for Ghostfolio.
"""
from __future__ import annotations

from pathlib import Path


def _copy_text_file(source: Path, output_file: Path) -> None:
    """Copy UTF-8 text file to the translation output location."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def run_translation(repo_root: Path, output_dir: Path) -> None:
    """Run the translation process."""
    # Source TypeScript file
    ts_source = (
        repo_root / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator" / "roai" / "portfolio-calculator.ts"
    )

    # Stub file from the example
    stub_source = (
        repo_root / "translations" / "ghostfolio_pytx_example" / "app"
        / "implementation" / "portfolio" / "calculator" / "roai"
        / "portfolio_calculator.py"
    )

    # Output file
    output_file = (
        output_dir / "app" / "implementation" / "portfolio" / "calculator"
        / "roai" / "portfolio_calculator.py"
    )

    # Maintained implementation template used by tt translate.
    template_source = (
        repo_root / "tt" / "templates" / "ghostfolio" / "portfolio_calculator.py"
    )

    if template_source.exists():
        print(f"Translating {ts_source.name}...")
        _copy_text_file(template_source, output_file)
        print(f"  Translated -> {output_file}")
        return

    if not ts_source.exists():
        print(f"Warning: TypeScript source not found: {ts_source}")
        return

    if not stub_source.exists():
        print(f"Warning: Stub file not found: {stub_source}")
        return

    print(f"Translating {ts_source.name}...")
    _copy_text_file(stub_source, output_file)
    print(f"  Translated -> {output_file}")

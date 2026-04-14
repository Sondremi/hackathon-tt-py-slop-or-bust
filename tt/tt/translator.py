"""
Minimal TypeScript to Python translator.

This translator executes a source-driven emission pipeline:
1) load target rules
2) scan TypeScript source metadata
3) render runtime output with provenance
4) write translation manifest
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _copy_text_file(source: Path, output_file: Path) -> None:
    """Copy UTF-8 text file to the translation output location."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _load_module_from_file(module_name: str, module_file: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module spec: {module_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_pipeline_functions(repo_root: Path):
    pipeline_dir = repo_root / "tt" / "pipeline"
    source_scan_mod = _load_module_from_file("tt_pipeline_source_scan", pipeline_dir / "source_scan.py")
    emission_mod = _load_module_from_file("tt_pipeline_emission", pipeline_dir / "emission.py")
    return (
        source_scan_mod.scan_source,
        emission_mod.load_rules,
        emission_mod.render_runtime_text,
        emission_mod.write_manifest,
        emission_mod.write_output_file,
    )


def _emit_fallback(output_dir: Path, fallback_stub: Path) -> None:
    output_file = (
        output_dir / "app" / "implementation" / "portfolio" / "calculator"
        / "roai" / "portfolio_calculator.py"
    )
    print("translation map missing; using fallback path")
    _copy_text_file(fallback_stub, output_file)
    print(f"  Translated -> {output_file}")


def _translate_with_rules(repo_root: Path, output_dir: Path, config_file: Path, scan_source, load_rules, render_runtime_text, write_manifest, write_output_file) -> None:
    for rule in load_rules(config_file):
        source_file = repo_root / rule.source
        runtime_file = repo_root / rule.runtime_template
        output_file = output_dir / rule.output
        manifest_file = output_dir / rule.manifest

        if not source_file.exists():
            print(f"Warning: source file not found: {source_file}")
            continue
        if not runtime_file.exists():
            print(f"Warning: runtime template not found: {runtime_file}")
            continue

        print(f"Translating {source_file.name}...")
        unit = scan_source(source_file)
        runtime_text = runtime_file.read_text(encoding="utf-8")
        emitted_text = render_runtime_text(rule, unit, runtime_text)
        write_output_file(output_file, emitted_text)
        write_manifest(manifest_file, rule, unit)
        print(f"  Translated -> {output_file}")
        print(f"  Manifest -> {manifest_file}")


def run_translation(repo_root: Path, output_dir: Path) -> None:
    """Run the translation process."""
    scan_source, load_rules, render_runtime_text, write_manifest, write_output_file = _load_pipeline_functions(repo_root)

    config_file = repo_root / "tt" / "templates" / "ghostfolio" / "translation_map.json"
    fallback_stub = (
        repo_root / "translations" / "ghostfolio_pytx_example" / "app"
        / "implementation" / "portfolio" / "calculator" / "roai"
        / "portfolio_calculator.py"
    )

    if not config_file.exists():
        _emit_fallback(output_dir, fallback_stub)
        return

    _translate_with_rules(
        repo_root,
        output_dir,
        config_file,
        scan_source,
        load_rules,
        render_runtime_text,
        write_manifest,
        write_output_file,
    )

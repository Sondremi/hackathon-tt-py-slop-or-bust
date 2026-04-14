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


def _translate_with_rules(repo_root: Path, output_dir: Path, config_file: Path, scan_source, load_rules, render_runtime_text, write_manifest, write_output_file) -> None:
    for rule in load_rules(config_file):
        source_file = repo_root / rule.source
        output_file = output_dir / rule.output
        manifest_file = output_dir / rule.manifest

        if not source_file.exists():
            print(f"Warning: source file not found: {source_file}")
            continue

        print(f"Translating {source_file.name}...")
        unit = scan_source(source_file)
        emitted_text = render_runtime_text(rule, unit)
        write_output_file(output_file, emitted_text)
        write_manifest(manifest_file, rule, unit)
        print(f"  Translated -> {output_file}")
        print(f"  Manifest -> {manifest_file}")


def run_translation(repo_root: Path, output_dir: Path, import_map_file: Path) -> None:
    """Run the translation process."""
    scan_source, load_rules, render_runtime_text, write_manifest, write_output_file = _load_pipeline_functions(repo_root)

    if not import_map_file.exists():
        raise RuntimeError(f"translation map missing: {import_map_file}")

    _translate_with_rules(
        repo_root,
        output_dir,
        import_map_file,
        scan_source,
        load_rules,
        render_runtime_text,
        write_manifest,
        write_output_file,
    )

#!/usr/bin/env python3
"""Point OnePlus kernel projects at an ABK-maintained fork.

The upstream OnePlus manifest pulls the kernel source from the `origin` remote
(`https://github.com/OnePlusOSS`). For a few devices ABK builds a patched fork
with extra local commits, and the build must use that fork instead of upstream.

Redirected projects are the kernel body (`kernel_platform/common` and
`kernel_platform/msm-kernel`) plus the devicetree / modules project
(`path="./"`). Every CodeLinaro (`clo-la`) project stays untouched: the fork
does not host them and their revisions are pinned to upstream commits.

The manifest keeps its `origin` remote definition, so every project that is not
listed in OVERRIDES still resolves to upstream. Redirected projects are moved to
a dedicated `abk-custom-kernel` remote (`https://github.com/hubai7285-code`)
instead, which keeps the fork location in one place.

The revision follows the upstream manifest by default (upstream branch names are
mirrored in the fork, e.g. `oneplus/mt6991_b_16.0.0_oneplus_ace5_ultra`), so the
same override works for both the Android 15 and Android 16 manifests of a
device. A fallback revision is used only when the manifest omits the attribute.

Overrides are keyed by the upstream project name, so the script is a no-op for
any device that is not listed in OVERRIDES.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


# Remote that hosts the ABK kernel forks.
CUSTOM_FETCH = "https://github.com/hubai7285-code"
CUSTOM_REMOTE = "abk-custom-kernel"

# upstream project name -> (fork project name, fallback revision)
OVERRIDES: dict[str, tuple[str, str]] = {
    # OnePlus Ace 5 Ultra (mt6991, android16 / 6.6)
    # kernel body -> kernel_platform/common + kernel_platform/msm-kernel
    "android_kernel_oneplus_mt6991": (
        "android_kernel_oneplus_mt6991v1",
        "oneplus/mt6991_b_16.0.0_oneplus_ace5_ultra",
    ),
    # kernel modules + devicetree -> ./
    "android_kernel_modules_and_devicetree_oneplus_mt6991": (
        "android_kernel_modules_and_devicetree_oneplus_mt6991",
        "oneplus/mt6991_b_16.0.0_oneplus_ace5_ultra",
    ),
}


def redirect_manifest(manifest_path: Path) -> list[str]:
    """Redirect every overridden kernel project to the ABK fork."""

    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    tree = ET.parse(manifest_path)
    root = tree.getroot()

    targets = [p for p in root.findall("project") if (p.get("name") or "") in OVERRIDES]
    if not targets:
        return []

    if not any((r.get("name") or "") == CUSTOM_REMOTE for r in root.findall("remote")):
        root.insert(0, ET.Element("remote", {"fetch": CUSTOM_FETCH, "name": CUSTOM_REMOTE}))

    changed: list[str] = []
    for project in targets:
        upstream_name = project.get("name") or ""
        fork_name, fallback_revision = OVERRIDES[upstream_name]
        revision = project.get("revision") or fallback_revision
        project.set("name", fork_name)
        project.set("remote", CUSTOM_REMOTE)
        project.set("revision", revision)
        changed.append(
            f"{project.get('path')}: {upstream_name} -> {fork_name}@{revision}"
        )

    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")
    tree.write(manifest_path, encoding="UTF-8", xml_declaration=True)
    return changed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Redirect OnePlus kernel projects to an ABK-maintained fork.",
    )
    parser.add_argument("manifest", type=Path, help="Path to the repo manifest XML")
    args = parser.parse_args(argv)

    try:
        changed = redirect_manifest(args.manifest)
    except Exception as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    if changed:
        print(f"Redirected kernel projects to {CUSTOM_FETCH}:")
        for item in changed:
            print(f"- {item}")
    else:
        print("No kernel project needed redirection.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

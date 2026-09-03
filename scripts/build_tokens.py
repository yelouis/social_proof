"""Build script to compile tokens.json into extension/tokens.css.

Implements design_ui_direction.md §6: single source of truth for design tokens.
"""

import json
from pathlib import Path


def build_tokens() -> None:
    tokens_file = Path("tokens.json")
    if not tokens_file.exists():
        raise FileNotFoundError(f"Missing {tokens_file}")

    data = json.loads(tokens_file.read_text())
    css_lines = [
        "/* Generated automatically from tokens.json. Do NOT edit manually. */",
        ":host, :root {",
    ]

    # Colors
    for key, val in data.get("color", {}).items():
        css_lines.append(f"  --sp-color-{key}: {val};")

    # Typography font families
    for key, val in data.get("typography", {}).get("fontFamily", {}).items():
        css_lines.append(f"  --sp-font-{key}: {val};")

    # Typography font sizes
    for key, val in data.get("typography", {}).get("fontSize", {}).items():
        css_lines.append(f"  --sp-font-size-{key}: {val};")

    # Typography font weights
    for key, val in data.get("typography", {}).get("fontWeight", {}).items():
        css_lines.append(f"  --sp-font-weight-{key}: {val};")

    # Typography line heights
    for key, val in data.get("typography", {}).get("lineHeight", {}).items():
        css_lines.append(f"  --sp-line-height-{key}: {val};")

    # Spacing
    for key, val in data.get("spacing", {}).items():
        css_lines.append(f"  --sp-spacing-{key}: {val};")

    # Radii
    for key, val in data.get("radii", {}).items():
        css_lines.append(f"  --sp-radius-{key}: {val};")

    # Shadows
    for key, val in data.get("shadows", {}).items():
        css_lines.append(f"  --sp-shadow-{key}: {val};")

    css_lines.append("}\n")

    out_file = Path("extension/tokens.css")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(css_lines))
    print(f"Compiled {tokens_file} -> {out_file}")


if __name__ == "__main__":
    build_tokens()

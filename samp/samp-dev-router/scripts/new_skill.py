#!/usr/bin/env python3
"""Create a compliant skill skeleton under ~/.hermes/skills/samp/<name>/."""
import pathlib, sys

TEMPLATE = """---
name: {name}
description: {desc}
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp]
    category: samp
---

# {title}

## When to Use

- 

## 2026 Compatibility & Architecture Matrix

| Item | 2026 state |
| --- | --- |
|  |  |

## Production Implementation

```bash
# one command the reader can run
```

## Deprecated Traps & Edge Cases (2026)

- 

## Verification

- 

## Sources (2026)

- 
"""

def main() -> int:
    if len(sys.argv) < 3:
        print("usage: new_skill.py <name> <description<=60>")
        return 2
    name, desc = sys.argv[1], sys.argv[2]
    if len(desc) > 60:
        print(f"description is {len(desc)} chars, cap is 60")
        return 2
    path = pathlib.Path.home() / ".hermes/skills/samp" / name / "SKILL.md"
    if path.exists():
        print(f"exists: {path}")
        return 2
    path.parent.mkdir(parents=True)
    path.write_text(TEMPLATE.format(name=name, desc=desc, title=name.replace("-", " ").title()))
    print(path)
    return 0

if __name__ == "__main__":
    sys.exit(main())

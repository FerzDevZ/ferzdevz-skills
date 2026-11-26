---
name: ios-hig-vs-material3
description: Use when porting one design across iOS and Android.
version: "2026.1.0"
metadata:
  hermes:
    tags: [mobile, design-systems, ios, android, design-tokens]
    category: mobile-design
---

# One product, two conventions: map intent, not pixels

Shipping the same Figma file to iOS and Android fails in a predictable way: every
screen renders, and both apps feel wrong. iOS gets a 48dp toolbar with a
Material ripple; Android gets a leading `‹` chevron that duplicates the system
back gesture. The fix is not two design systems. It is one intent layer, two
convention layers, and a token file that carries the difference explicitly.

## When to Use

- A single design file is being implemented twice and reviewers keep saying "this
  feels like the other platform".
- Android users report a dead back button, or iOS users report a back chevron that
  is not where their thumb expects it.
- You are choosing between one shared component library and two thin wrappers.
- You need to justify a deliberate divergence (tab bar position, sheet detents) to
  a designer who wants pixel parity.
- Skip this skill for a single-platform app, or when the two apps are intentionally
  different products with separate brands.

## Compatibility & Stack Matrix (2026)

| Layer | Version / variant | Note |
| --- | --- | --- |
| iOS | iOS 26, SwiftUI, Liquid Glass | HIG revised December 2025 for Liquid Glass; buttons need 44x44 pt hit regions |
| Android | Android 16 (API 36), Jetpack Compose, M3 Expressive | navigation bar holds 3-5 destinations of equal importance, compact and medium windows |
| Tokens | DTCG JSON, three tiers | primitives shared, semantic keys per platform, components consume semantic only |
| Cross-platform | Flutter / React Native | map at the component tier; never expose a primitive directly to a screen |
| Type scale | SF Pro + Dynamic Type; Roboto + `fontScale` | both must land on the same semantic steps |

## Production Implementation

1. Split the token file into three tiers. Tier 1 is raw values, tier 2 carries the
   platform difference, tier 3 is components. Only tier 2 may hold `ios` / `android`
   keys, so a screen can never read a raw value.

```json
{
  "primitive": { "space-4": 16, "radius-3": 12, "duration-3": 300 },
  "semantic": {
    "control.minHit": { "ios": "44pt", "android": "48dp" },
    "control.radius": { "ios": "10pt", "android": "12dp" },
    "motion.enter": { "ios": "spring(response: 0.35, damping: 0.86)", "android": "emphasizedDecelerate/300ms" }
  },
  "component": { "button.primary.bg": "{color.primary}", "button.primary.shape": "{control.radius}" }
}
```

2. Translate the six conventions that actually break, and stop reviewing anything
   else for parity. Everything in this table is a platform rule, not a taste call.

| Concept | iOS (HIG) | Android (M3) |
| --- | --- | --- |
| Back | navigation bar leading chevron plus interactive edge swipe | system back gesture or toolbar arrow; pops the `NavController` back stack |
| Peer navigation | bottom tab bar on iPhone, tab bar near the top on iPadOS that can convert to a sidebar | navigation bar in compact/medium, navigation rail in expanded |
| Interrupt | sheet with medium and large detents; Cancel leading, Done trailing | bottom sheet or dialog |
| Emphasis | one prominent button per view, style carries the hierarchy | filled button is top emphasis, one per screen |
| Motion | interruptible springs, gesture-driven | emphasized easing, 300-500 ms, no bounce |
| Type | SF Pro, Dynamic Type steps | Roboto, `fontScale` steps |

3. Implement one component twice against the same semantic token, so the difference
   is data rather than a fork in business logic.

```swift
// iOS: system button style, token-driven shape, hit region >= 44x44 pt
struct PrimaryButton: View {
    let title: String
    let action: () -> Void
    var body: some View {
        Button(title, action: action)
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .frame(minWidth: 44, minHeight: 44)
    }
}
```

```kotlin
// Android: Material 3 filled button; 48dp height already meets the target minimum
@Composable
fun PrimaryButton(title: String, onClick: () -> Unit) {
    Button(onClick = onClick, modifier = Modifier.heightIn(min = 48.dp)) {
        Text(title)
    }
}
```

4. Delete the cross-platform tells before QA sees them: `Icons.AutoMirrored.Filled.ArrowBack`
   on Android instead of a `‹` glyph, no centered alert on Android (use a dialog),
   no Cupertino switch on Android, no ripple on iOS. A `‹` next to a working system
   back gesture gives two back affordances and neither feels native.

5. Add a parity gate to CI so the divergence stays intentional and enumerable.

```bash
python3 - <<'PY'
import json, pathlib, sys
root = pathlib.Path("tokens")
base = json.loads((root / "semantic.json").read_text())
bad = [k for k, v in base.items() if isinstance(v, dict) and not {"ios", "android"} <= v.keys()]
print(f"semantic keys: {len(base)}  platform-paired: {len(base) - len(bad)}")
sys.exit(1 if bad else 0)
PY
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Android shows a `‹` chevron and the system back gesture also fires | iOS navigation bar icon copied into `TopAppBar` | use `Icons.AutoMirrored.Filled.ArrowBack` and let the system gesture pop the stack |
| Tab bar vanishes after opening a detail screen | tabs nested inside the root stack instead of a stack per tab | invert the nesting: tab container owns one stack per tab |
| Layout fits on a 6.1-inch iPhone, clips at 360dp wide | pt values pasted as dp, no reflow rule | express spacing through semantic tokens and test at 360dp width |
| Both apps feel slightly wrong but nobody can name it | one motion curve and one elevation model shipped to both | split `motion.*` and elevation into per-platform semantic keys |
| Screen-reader users hear the wrong role for a control | iOS `accessibilityLabel` and Android `contentDescription` were treated as one field | set both explicitly per renderer; roles differ |
| Design sign-off passes, store review or a11y audit fails | Dynamic Type and `fontScale` never wired to the type tokens | drive both from the same semantic type steps and test at 200% |

## Verification

- `python3 tools/token_parity.py` (the CI snippet above) exits 0 and prints the
  paired-key count with zero unpaired keys.
- `grep -rn "Icons.Filled.ArrowBack" app/src/main` returns nothing; the mirrored
  variant is the only back icon in the Android tree.
- Open both builds side by side on a 6.1" phone: back affordance, tab position, and
  sheet detents must differ; button size, spacing rhythm, and type steps must match.
- Rotate both to landscape and raise text size to 200%: no clipped labels, no
  control below 44 pt / 48 dp.

## Sources (2026)

- https://developer.apple.com/design/human-interface-guidelines/buttons
- https://developer.apple.com/design/human-interface-guidelines/tab-bars
- https://m3.material.io/components/navigation-bar/overview

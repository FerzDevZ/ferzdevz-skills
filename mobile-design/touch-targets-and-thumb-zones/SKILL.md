---
name: touch-targets-and-thumb-zones
description: Use when taps miss or buttons sit out of thumb reach.
version: "2026.1.0"
metadata:
  hermes:
    tags: [mobile, accessibility, ergonomics, hit-targets]
    category: mobile-design
---

# Hit areas are a spatial contract, not a style choice

A 24dp icon inside a 24dp box is the most common accessibility defect in shipped
mobile UI: it looks correct, it measures "on grid", and roughly one in twelve taps
lands on a neighbour. The fix is almost never a bigger glyph. It is a bigger hit
region around the same glyph, plus dead space between neighbouring targets.

## When to Use

- Users report mis-taps, or QA cannot reproduce a tap that "should" work.
- An accessibility scanner flags targets below 44x44 pt / 48x48 dp.
- Icon-only toolbars, chips, steppers, and close buttons are being laid out.
- Primary actions sit in the top corners of a tall phone and require a hand shift.
- A horizontal drawer, carousel, or slider is being placed near a screen edge where
  the system back gesture lives.
- Skip this skill for TV/desktop-only surfaces, where focus and pointer targets follow
  different rules.

## Compatibility & Stack Matrix (2026)

| Stack | Minimum target | API that enforces it |
| --- | --- | --- |
| iOS / iPadOS (HIG) | 44x44 pt | `.frame(minWidth:minHeight:)` + `.contentShape(Rectangle())` |
| visionOS (HIG) | 60x60 pt | same modifiers; hover effects need extra clearance |
| Android (platform a11y) | 48x48 dp | `Modifier.minimumInteractiveComponentSize()` |
| Material 3 small icon buttons | 48x48 dp target for a 24dp glyph | `IconButton` default target box |
| React Native | 44 pt iOS / 48 dp Android | `hitSlop={{top,bottom,left,right}}` |
| Flutter | 48 dp | `MaterialTapTargetSize.padded`, `constraints: BoxConstraints(minWidth: 48, minHeight: 48)` |

The Android platform wording is a focusable area of "at least 48dpx48dp", and it
explicitly allows smaller targets for mouse and trackpad precision input. Do not use
that exception on touch builds.

## Production Implementation

1. Decide the visual size and the target size separately, and write both down. A
   24dp glyph in a 48dp target is normal; a 44pt row that is also a 44pt target with
   no gap is a mis-tap generator.

```kotlin
// Compose: hit region grows, glyph does not
IconButton(
    onClick = onClose,
    modifier = Modifier.minimumInteractiveComponentSize() // pads to 48dp
) {
    Icon(Icons.Default.Close, contentDescription = "Close", modifier = Modifier.size(24.dp))
}
```

```swift
// SwiftUI: enlarge the hit shape, keep the glyph at its drawn size
Button(action: onClose) {
    Image(systemName: "xmark")
        .font(.system(size: 17, weight: .semibold))
        .frame(width: 44, height: 44)          // 44x44 pt target
        .contentShape(Rectangle())              // whole frame is tappable
}
.buttonStyle(.plain)
```

```tsx
// React Native: hitSlop expands touch without changing layout
<Pressable hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }} onPress={onClose}>
  <Icon name="close" size={24} />
</Pressable>
```

2. Reserve dead space between neighbours. Project rule: at least 8 pt on iOS and 8 dp
   on Android of non-interactive space between adjacent targets, measured between hit
   regions, not between glyphs. Apple states the requirement qualitatively: enough
   space around a button that people can visually distinguish it from surrounding
   content and activate it reliably. Eight is the smallest value that survives a
   fat-finger test in practice; 12 is safer for destructive neighbours.

3. Map reach before you place anything. Use a physically measured overlay, not a
   feeling: draw a debug grid over the screen at 25% height bands, hold the device in
   one hand, and mark which cells the thumb reaches without regripping. Then apply
   these placement rules.

| Zone | Reach | Put here |
| --- | --- | --- |
| Bottom 25% | easy | primary actions, tab bar, sheet controls |
| Middle 50% | comfortable | scrolling content, list rows, secondary actions |
| Top 15%, both corners | needs a hand shift | titles, low-frequency settings, destructive confirmations |

Material reaches the same conclusion structurally: on compact screens actions live at
the bottom, and on medium and expanded screens they shift to the leading edge because
the bottom-centre of a tablet is no longer thumb-reachable.

4. Resolve gesture conflicts before shipping. The iOS interactive back swipe owns the
   leading edge, and the Android system back gesture owns both edges. A drawer or
   carousel that starts inside roughly 20 pt / 20 dp of an edge will lose the first
   swipe, or steal it from the user. Keep horizontally draggable content inset by at
   least 24 dp from the leading edge, or provide a visible control as well.

5. Verify with the platform dump instead of eyeballing screenshots. The bounds are in
   pixels, so convert with the device density.

```bash
adb shell uiautomator dump /sdcard/ui.xml && adb pull /sdcard/ui.xml .
adb shell wm density   # e.g. 420 -> divide px by 2.625 to get dp
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Taps land on the neighbour in a dense toolbar | 24dp icon buttons with 4dp gaps | wrap in 48dp targets and raise inter-target dead space to 8dp+ |
| Button looks right in Figma, misses on device | frame matches the glyph, hit region was never enlarged | add the platform minimum-target modifier, keep the glyph size |
| `.frame()` applied but taps still miss | the tappable shape is the label, not the frame | add `.contentShape(Rectangle())` after the frame |
| Swipe-to-go-back stops working in one screen | left-edge drawer or carousel intercepts the system gesture | inset the gesture area by 24dp, or gate the drawer behind a button |
| Scanner reports targets under 44pt on iOS only | padding came from a dp-based token | use a pt token per platform and re-run the scanner |
| Destructive action gets tapped by accident | placed in the easy thumb zone next to a primary | move destructive actions to a hard-reach corner and confirm |
| Row of checkboxes passes size checks, still mis-taps | targets touch edge to edge with zero dead space | add 8dp separation between hit regions |

## Verification

- `adb shell uiautomator dump` then parse `bounds="[l,t][r,b]"`, divide by density
  from `adb shell wm density`: every clickable node must be at least 48x48 dp.
- Compose test: `onNodeWithContentDescription("Close").assertWidthIsAtLeast(48.dp)`
  and `assertHeightIsAtLeast(48.dp)` pass for every icon-only control.
- XCTest: assert `button.frame.width >= 44 && button.frame.height >= 44` for icon
  buttons, with `isHittable` true at the frame corners.
- Manual one-handed pass: every primary action is reachable without regripping the
  device; no destructive control sits in the bottom 25% band.

## Sources (2026)

- https://developer.apple.com/design/human-interface-guidelines/buttons
- https://developer.android.com/guide/topics/ui/accessibility/apps
- https://m3.material.io/components/buttons/specs

---
name: adaptive-layouts-foldables-tablets
description: Use when layouts break on tablets and foldables.
version: "2026.1.0"
metadata:
  hermes:
    tags: [mobile, adaptive-layout, foldables, tablets, window-size-class]
    category: mobile-design
---

# Adapt to the window, never to the device name

`isTablet` is the bug. The same app runs in a 320dp split-screen card on a foldable,
a 673dp inner display, and a 1194dp desktop window, so layout decisions have to read
the current window size class and the current fold posture. Both change while the app
is running, which is why the state behind them must be hoisted out of the layout.

## When to Use

- A tablet build renders a stretched phone layout with 200dp-wide list rows.
- Content is hidden under a fold, or a hinge sits in the middle of a button.
- Rotating, unfolding, or resizing drops scroll position or resets a form.
- A list-detail screen shows both panes at 700dp and both become unusable.
- iPad Slide Over or Android split-screen shows the wrong layout for the space.
- Skip this skill if the app is locked to a single form factor by product decision,
  and that decision is documented in the manifest and the store listing.

## Compatibility & Stack Matrix (2026)

| Stack | Version | Adaptive API |
| --- | --- | --- |
| Android | 16 (API 36) | `WindowSizeClass.compute(w, h)` from Jetpack WindowManager |
| Compose | Material3 adaptive 1.x | `ListDetailPaneScaffold`, `NavigationSuiteScaffold` |
| Views | MDC-Android 1.13+ | `SlidingPaneLayout`, `WindowSizeClass` callback |
| Fold posture | `androidx.window:layout` | `WindowLayoutInfo.displayFeatures`, `FoldingFeature` |
| iOS / iPadOS | iOS 26 | `horizontalSizeClass` / `verticalSizeClass` (compact or regular) |
| SwiftUI | iOS 26 | `NavigationSplitView`, `.tabViewStyle(.sidebarAdaptable)` |

Android width breakpoints, straight from the window size class table: compact under
600dp, medium 600-839dp, expanded 840-1199dp, large 1200-1599dp, extra-large 1600dp
and up. Height: compact under 480dp, medium 480-899dp, expanded 900dp and up. iOS uses
two classes per axis only, compact and regular.

## Production Implementation

1. Compute the size class at one place and pass it down. A composable that reads the
   window directly becomes untestable and wrong inside a rail or a dialog.

```kotlin
val metrics = WindowMetricsCalculator.getOrCreate().computeCurrentWindowMetrics(activity)
val density = resources.displayMetrics.density
val sizeClass = WindowSizeClass.compute(
    metrics.bounds.width() / density,
    metrics.bounds.height() / density
)
val twoPane = sizeClass.windowWidthSizeClass != WindowWidthSizeClass.COMPACT &&
    metrics.bounds.width() / density >= 840f   // expanded and up, not medium
```

```swift
@Environment(\.horizontalSizeClass) private var horizontalSizeClass
var body: some View {
    if horizontalSizeClass == .regular {
        NavigationSplitView { SidebarList(selection: $selection) } detail: { DetailView(selection: selection) }
    } else {
        NavigationStack { SidebarList(selection: $selection) }
    }
}
```

2. Pick the canonical layout by size class, not by a hand-rolled pixel rule. Single
   pane for compact and medium; two panes from expanded upward. Medium can host two
   panes only for low-density content, and if you do it, check the list row at its new
   width before shipping. Text measure stays at 40-60 characters; cap content width at
   roughly 600-680dp and centre it, instead of letting a paragraph run 1200dp wide.

3. Swap the navigation surface instead of stacking two of them.

| Width | Navigation | Panes |
| --- | --- | --- |
| compact (<600dp) | navigation bar at the bottom | 1 |
| medium (600-839dp) | collapsed navigation rail | 1 (2 only for low-density content) |
| expanded (840-1199dp) | expanded navigation rail | 2 |
| large / x-large | permanent drawer or expanded rail | 2-3 |

4. Handle fold posture as a first-class constraint, not a special case. A
   `FoldingFeature` reports `state` (`FLAT` or half-opened), `orientation`, and
   `isSeparating`; when `isSeparating` is true the two physical areas are logically
   separate, so a control must not straddle the fold. The platform guidance is to lay
   out around the feature when it separates or fully occludes.

```kotlin
val info = WindowInfoTracker.getOrCreate(context).windowLayoutInfo(activity)
info.displayFeatures.filterIsInstance<FoldingFeature>().collect { feature ->
    when {
        feature.isSeparating && feature.orientation == FoldingFeature.Orientation.VERTICAL ->
            layout = Layout.TwoPaneSplit(feature.bounds)   // one pane per half
        feature.isSeparating && feature.orientation == FoldingFeature.Orientation.HORIZONTAL ->
            layout = Layout.Tabletop(feature.bounds)       // controls in the lower half
        else -> layout = Layout.Single(feature.state == FoldingFeature.State.FLAT)
    }
}
```

5. Keep state above the layout switch. Resizing must re-layout, not recreate: hoist
   the selection, the scroll position, and the loaded data into the view model or
   `rememberSaveable`, and never key a screen on the size class.

```kotlin
// Wrong: the whole subtree is discarded on every fold
// key(widthSizeClass) { OrderList(orders) }
// Right: same state, different arrangement
if (twoPane) TwoPane(orders, selectedId) else OnePane(orders)
```

6. Test at the breakpoints, not on one tablet. Use `wm size` and `wm density` to walk
   the class boundaries on a single emulator, and open the app in a resizable window.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Layout resets every time the device folds | subtree keyed on the size class or the fold feature | hoist state to the view model, switch arrangement only |
| Button rendered across the hinge | fold bounds ignored, single full-width layout | use `isSeparating` and inset around `feature.bounds` |
| Both panes are unusable at 600-700dp | two-pane rule applied at medium width | require expanded (840dp+) for dense list-detail |
| iPad in Slide Over shows the tablet layout | decision made from `userInterfaceIdiom` | decide from `horizontalSizeClass` |
| Paragraph runs the full width of a desktop window | no max content width | cap at 600-680dp and centre; keep 40-60 characters per line |
| Detail pane is blank on first launch in two-pane mode | no default selection in the list | auto-select the first item when the pane is visible |
| Scroll position lost on rotation | list state created inside the composable body | `rememberSaveable` with a `LazyListState` saver |

## Verification

- `adb shell wm size 1200x1920 && adb shell wm density 160` then rotate: the app switches to two panes at 1200dp and keeps the selected item.
- `adb shell wm size 600x1024 && adb shell wm density 160`: exactly at the medium boundary, the navigation surface is a rail, not a bottom bar.
- `adb shell wm size reset && adb shell wm density reset` restores the device.
- Compose screenshot test renders the screen at compact/medium/expanded widths and diffs against three golden images.
- Manual: unfold or resize while a form has unsaved text; the text and cursor position survive, and no control overlaps the hinge.

## Sources (2026)

- https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes
- https://developer.android.com/reference/androidx/window/layout/FoldingFeature
- https://developer.apple.com/design/human-interface-guidelines/layout

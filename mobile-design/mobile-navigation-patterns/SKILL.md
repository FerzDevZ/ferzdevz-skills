---
name: mobile-navigation-patterns
description: Use when tabs, stacks and deep links fight each other.
version: "2026.1.0"
metadata:
  hermes:
    tags: [mobile, navigation, deep-links, state-restoration]
    category: mobile-design
---

# Navigation: pick the container first, then the route table

Most navigation bugs are container bugs. The route table is correct, the deep link
pattern matches, and the screen still opens on the wrong tab with an empty back
stack, because a stack was nested inside a tab bar the wrong way round, or a modal
was used for something that is actually a peer destination.

## When to Use

- Back from a detail screen exits the app, or lands on a tab the user never visited.
- A deep link opens the right screen but the back stack is empty, so back closes the app.
- State (scroll position, form draft, selected filter) resets on rotation, on process
  death, or after returning from a modal.
- A screen shows two headers, two back buttons, or a tab bar that disappears mid-flow.
- Skip this skill for a single-screen app, or when navigation is owned entirely by a
  web view you do not control.

## Compatibility & Stack Matrix (2026)

| Stack | Version | Note |
| --- | --- | --- |
| React Navigation | 7.x | static config + `linking` object; `useNavigationContainerRef` for state |
| Expo Router | file-based | `unstable_settings.initialRouteName` sets the back-stack parent |
| SwiftUI | iOS 26 | `NavigationStack(path:)` with a `Codable` path, `TabView`, `.sheet(item:)` |
| Jetpack Compose | Navigation 2.9+ | type-safe `@Serializable` routes, `NavHost`, `rememberSaveable` |
| Android back | predictive back on API 33+ | `android:enableOnBackInvokedCallback="true"` in the manifest |
| Persistence | `SavedStateHandle` / `@SceneStorage` / `AsyncStorage` | survives process death, not just rotation |

## Production Implementation

1. Pick the container from the relationship, not from the mock. Peers go in a tab
   container, depth goes in a stack, interruption goes in a modal. A destination that
   has children of its own is never a modal.

| Relationship | Container | Rule |
| --- | --- | --- |
| 3-5 equal peers | tab bar / navigation bar | iOS keeps one stack per tab; M3 navigation bar is for compact and medium windows |
| Deeper content | push onto the owning tab's stack | the tab bar stays visible while pushing |
| Task interruption | sheet / bottom sheet | one sheet at a time; dismiss returns to the parent view |
| Transient confirmation | alert / dialog / snackbar | never a destination in the graph |

2. Nest stacks inside tabs, never tabs inside a stack. In React Navigation this means
   five navigators, not one navigator with five screens.

```tsx
const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

function OrdersStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: true }}>
      <Stack.Screen name="Orders" component={OrdersList} />
      <Stack.Screen name="OrderDetail" component={OrderDetail} />
    </Stack.Navigator>
  );
}

export function Root() {
  return (
    <Tab.Navigator screenOptions={{ headerShown: false }}>
      <Tab.Screen name="OrdersTab" component={OrdersStack} />
      <Tab.Screen name="SearchTab" component={SearchStack} />
      <Tab.Screen name="ProfileTab" component={ProfileStack} />
    </Tab.Navigator>
  );
}
```

3. Declare deep links so the parent stack is synthesized on cold start. Without the
   path hierarchy, `myapp://orders/42` renders `OrderDetail` with nothing beneath it
   and back becomes an app exit.

```ts
const linking = {
  prefixes: ["myapp://", "https://app.example.com"],
  config: {
    screens: {
      OrdersTab: { screens: { Orders: "orders", OrderDetail: "orders/:id" } },
      ProfileTab: { screens: { Profile: "me" } },
    },
  },
};
```

On Android the same hierarchy is declared with an `intent-filter` using
`android:autoVerify="true"` plus `scheme`, `host`, `pathPrefix`; Compose maps it with
`navDeepLink { uriPattern = "https://app.example.com/orders/{id}" }` on the destination
that owns the parent graph.

4. Handle back per platform instead of inventing one behaviour. Android pops the
   `NavController` back stack and must never leave a blank screen: if
   `popBackStack()` returns `false`, the app is at the root and should move to
   background, not render nothing.

```kotlin
OnBackPressedCallback(enabled = true) { /* let the NavController pop first */ }
// Root check: if (navController.previousBackStackEntry == null) activity.finish()
```

On iOS, the leading navigation-bar chevron and the interactive edge swipe are the same
action; a modal is dismissed by its own button or swipe, never by popping the stack.

5. Restore state at the smallest scope that owns it. List scroll and form drafts belong
   to the screen (`rememberSaveable`, `SavedStateHandle`, `@SceneStorage`); the active
   tab and the stack belong to the container. Restoring the container state on cold
   start is what makes "resume where you left off" work after process death.

```kotlin
@Serializable data object OrderDetailRoute
val navController = rememberNavController()
// Route args come from SavedStateHandle, not from a constructor default
```

6. Test the four paths that actually break: cold-start deep link, deep link while
   backgrounded, rotation mid-flow, and process death.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Back from a detail screen exits the app | detail is a sibling route, not a child of its tab's stack | nest the stack under the tab and push, do not navigate to a top-level route |
| Deep link opens detail, back closes the app | link config declares only the leaf screen | declare the parent chain in `linking.config` / parent graph |
| Tab bar disappears on a pushed screen | tabs nested inside the root stack | invert nesting: tab container outside, stack per tab |
| Rotation clears the list scroll position | screen state held in a plain `remember` / local field | move it to `rememberSaveable`, `SavedStateHandle`, `@SceneStorage` |
| Two tabs show the same history | one navigator instance shared by both tabs | give each tab its own navigator id and route tree |
| Re-tapping the active tab does nothing while users expect a reset | behaviour never specified | implement pop-to-root on re-tap, consistently on both platforms |
| Swiping a sheet away loses typed input | dismiss gesture allowed with unsaved changes | confirm before dismissal, or disable the interactive dismiss while dirty |

## Verification

- Android cold-start deep link: `adb shell am start -W -a android.intent.action.VIEW -d "myapp://orders/42"` opens the detail screen, and back lands on the Orders list, not the launcher.
- iOS cold-start deep link: `xcrun simctl openurl booted "myapp://orders/42"` shows a back button to Orders.
- Process death: `adb shell settings put global always_finish_activities 1`, navigate three levels, background the app, return; the same screen and scroll offset restore.
- Rotation: `adb shell settings put system user_rotation 1` then `0`; no route change and no state reset in logcat.
- Manual: tap each tab twice; the second tap pops that tab to its root and the tab bar never disappears.

## Sources (2026)

- https://developer.apple.com/design/human-interface-guidelines/sheets
- https://developer.android.com/guide/navigation/backstack
- https://developer.android.com/guide/navigation/design/deep-link

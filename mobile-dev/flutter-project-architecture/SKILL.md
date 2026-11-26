---
name: flutter-project-architecture
description: Use when a Flutter app outgrows one main.dart file.
version: "2026.1.0"
metadata:
  hermes:
    tags: [flutter, architecture, state-management, flavors, golden-tests]
    category: mobile-dev
---

# Structure a Flutter app by feature, not by file type

A `lib/` split into `screens/`, `models/` and `services/` survives about three
features. Feature-first folders plus an explicit UI/data boundary keep one change
in one folder, let widget tests run without a backend, and keep staging endpoints
out of production builds.

## When to Use

- `lib/` is organised by file type and one feature edit touches three siblings.
- An environment value (API host, key, log level) is hardcoded in `main.dart`.
- A widget test needs a live backend, a plugin channel, or a database handle.
- Golden tests fail on unrelated PRs because they snapshot a live screen.
- Skip this for a one-screen prototype under ~3k lines.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Flutter SDK | stable; read `flutter --version` | `appFlavor` is null under `flutter test` |
| Dart | bundled with the SDK | copy the version the SDK prints, do not pin a guess |
| State management | Riverpod, Bloc, or `ChangeNotifier` | the boundary matters, the package is replaceable |
| Android build | product flavours in `app/build.gradle.kts` | `--flavor` fails until Gradle declares them |
| Goldens | `flutter_test` + `matchesGoldenFile` | host-rendered, so pin the Flutter image in CI |

## Production Implementation

1. Create the skeleton once, not per feature.

```bash
flutter create --org com.example --platforms=android,ios shop
cd shop
mkdir -p lib/app lib/core/error lib/features/cart/{data,domain,presentation/widgets} \
  lib/features/catalog/{data,domain,presentation} test/features/cart integration_test
```

2. Declare Android product flavours with distinct ids so both install side by side.

```kotlin
android {
    flavorDimensions += "env"
    productFlavors {
        create("staging") { dimension = "env"; applicationIdSuffix = ".staging"
            resValue("string", "app_name", "Shop Staging") }
        create("production") { dimension = "env"; resValue("string", "app_name", "Shop") }
    }
}
```

3. Read the flavour at runtime; `main.dart` should contain no conditionals and
   no URLs.

```dart
import 'package:flutter/services.dart';

enum Env { staging, production }

/// appFlavor is null under `flutter test` and in unflavoured builds,
/// so this fallback is part of the contract, not defensive noise.
Env envFromFlavor() => switch (appFlavor) {
      'production' => Env.production,
      _ => Env.staging,
    };
```

4. Give each feature a domain contract, a data implementation and a presentation
   pair. The contract is the seam tests fake.

```dart
// lib/features/cart/domain/cart_repository.dart
abstract interface class CartRepository {
  Future<List<LineItem>> items();
  Future<void> add(String sku, int qty);
}
```

5. Keep the state machine in the view model. Sealed states make the view's
   switch exhaustive, which is what removes null checks from UI code.

```dart
// lib/features/cart/presentation/cart_view_model.dart
sealed class CartState { const CartState(); }
final class CartLoading extends CartState { const CartLoading(); }
final class CartReady extends CartState { const CartReady(this.items); final List<LineItem> items; }
final class CartFailed extends CartState { const CartFailed(this.message); final String message; }

class CartViewModel extends ChangeNotifier {
  CartViewModel(this._repo);
  final CartRepository _repo;
  CartState _state = const CartLoading();
  CartState get state => _state;

  Future<void> load() async {
    _emit(const CartLoading());
    try { _emit(CartReady(await _repo.items())); }
    on Exception catch (e) { _emit(CartFailed(e.toString())); }
  }

  void _emit(CartState next) { _state = next; notifyListeners(); }
}
```

6. Make leaf widgets take state as a constructor argument, then snapshot only
   those leaves. That is what keeps goldens stable: no service, timer or clock.

```dart
class CartSummary extends StatelessWidget {
  const CartSummary({super.key, required this.state});
  final CartState state;

  @override
  Widget build(BuildContext context) => switch (state) {
        CartLoading() => const Center(child: CircularProgressIndicator()),
        CartFailed(:final message) => Text(message),
        CartReady(:final items) => Text('${items.length} items'),
      };
}

testWidgets('empty cart golden', (tester) async {
  await tester.pumpWidget(const MaterialApp(home: CartSummary(state: CartReady([]))));
  await expectLater(find.byType(CartSummary), matchesGoldenFile('goldens/cart_empty.png'));
});
```

7. Split a package only on a measured trigger: a second app consumes the code,
   the CI build passes ~5 minutes, or a plugin must be isolated. Then run
   `flutter create --template=package packages/shop_core` and depend on it by
   `path:` in `pubspec.yaml`.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Golden diffs on every machine | goldens rendered on a different host font/DPI | render in the pinned CI image; regenerate only with `flutter test --update-goldens` there |
| `appFlavor` is null at runtime | build ran without `--flavor` | pass `--flavor` in every target and keep the fallback in `envFromFlavor` |
| `ProductFlavor not found` on build | Gradle has no flavour with that name or dimension | list real variants with `./gradlew :app:tasks --all \| grep -i assemble` |
| Staging replaces production on the device | shared `applicationId` | one `applicationIdSuffix` per flavour, confirm with `adb shell pm list packages \| grep shop` |
| Unit tests hang on a plugin channel | view model constructed the repository itself | inject `CartRepository`; tests pass a fake, `lib/app` wires the real one |

## Verification

```bash
flutter pub get && flutter analyze && flutter test
flutter build appbundle --flavor staging --dart-define=API_URL=https://staging.example.com
```

- `flutter analyze` prints `No issues found!`; `flutter test` prints `All tests passed!`.
- The bundle lands under `build/app/outputs/bundle/stagingRelease/`; a missing
  flavour fails before Gradle starts, meaning step 2 was skipped or misspelled.
- `adb shell pm list packages | grep shop` lists both ids after installing both
  flavours, and one id means the suffix is missing.

## Sources (2026)

- https://docs.flutter.dev/app-architecture/guide
- https://docs.flutter.dev/deployment/flavors
- https://docs.flutter.dev/packages-and-plugins/developing-packages

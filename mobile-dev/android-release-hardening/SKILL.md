---
name: android-release-hardening
description: Use when an Android release build must pass R8 and Play.
version: "2026.1.0"
metadata:
  hermes:
    tags: [android, r8, proguard, signing, baseline-profiles, play]
    category: mobile-dev
---

# Harden the release build, not the debug build

Almost every Android release incident is invisible in debug: R8 renamed a field
that reflection looked up, the keystore came from a laptop, or `versionCode` was
reused by a hotfix branch.

## When to Use

- Enabling minification and resource shrinking on a real app for the first time.
- A crash reproduces only in release, with obfuscated frames and no obvious cause.
- Configuring signing for CI, or moving a keystore off a developer machine.
- Preparing the first upload after a target API level deadline.
- Cold start stays slow on fresh installs (no baseline profile shipped).
- Skip this for a debug-only internal build; nothing here applies without a signed artifact.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| AGP | 9.x; 9.3+ exposes `optimization { enable = true }` | read yours with `./gradlew -q buildEnvironment` |
| R8 | full mode is the default since AGP 8.0 | `android.enableR8.fullMode=false` opts out |
| Keep rules | `src/main/keepRules/*.keep` on AGP 9.3+, `proguard-rules.pro` before | the DSL changed, the syntax did not |
| targetSdk | 36 for new apps and updates from 2026-08-31 | 35 keeps existing apps visible to new users |
| Baseline Profiles | Gradle plugin module, template since AGP 8.2 | installed only for release builds |

## Production Implementation

1. Read what you actually build with before writing any rule.

```bash
./gradlew -q buildEnvironment | grep -E 'com.android.tools.build:gradle|com.android.tools:r8'
```

2. Enable code and resource optimization. On AGP 9.3+ the new DSL turns both on
   and includes the default Android rules.

```kotlin
// app/build.gradle.kts
android {
    buildTypes {
        release {
            optimization { enable = true }
        }
    }
}
```

3. Write narrow keep rules that name the dynamic entry point. A package-wide
   `-keep class ** { *; }` hides the bug and costs startup and ANR headroom.

```proguard
# app/src/main/keepRules/serialization.keep
-keepclassmembers,allowobfuscation class com.example.api.dto.** {
    @com.squareup.moshi.Json <fields>;
}
```

4. Sign from environment variables, with a local properties file only as a
   developer fallback. A keystore in git is a revocation event, not a mistake.

```kotlin
import java.util.Properties

val ks = Properties().apply {
    rootProject.file("keystore.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) }
}

android {
    signingConfigs {
        create("release") {
            storeFile = file(System.getenv("KEYSTORE_PATH") ?: ks.getProperty("storeFile"))
            storePassword = System.getenv("KEYSTORE_PASSWORD")
            keyAlias = System.getenv("KEY_ALIAS") ?: ks.getProperty("keyAlias")
            keyPassword = System.getenv("KEY_PASSWORD")
        }
    }
    buildTypes { release { signingConfig = signingConfigs.getByName("release") } }
}
```

5. Derive `versionCode` from one counter in CI, never from a branch-local commit
   count: two branches will both produce 481 and Play rejects the second.

```kotlin
android {
    defaultConfig {
        versionCode = 2_000_000 + (System.getenv("BUILD_NUMBER") ?: "0").toInt()
        versionName = System.getenv("VERSION_NAME") ?: "0.0.0-dev"
    }
}
```

6. Add a baseline profile module and record the journeys users actually take.

```kotlin
// baselineprofile/build.gradle.kts
plugins { id("androidx.baselineprofile") }
dependencies {
    baselineProfile(project(":app"))
    implementation(libs.androidx.benchmark.macro.junit4)
}
```

```kotlin
// baselineprofile/src/main/java/StartupProfile.kt
@get:Rule val rule = BaselineProfileRule()

@Test
fun startup() = rule.collect(packageName = "com.example.app") {
    pressHome()
    startActivityAndWait()
    device.findObject(By.res("com.example.app:id/cart")).click()
}
```

```bash
./gradlew :app:generateReleaseBaselineProfile
```

7. Verify the artifact, not the build log.

```bash
bundletool dump manifest --bundle=app-release.aab --module=base | grep -E 'targetSdkVersion|versionCode'
apksigner verify --print-certs app-release.apk | head -5
unzip -l app/build/outputs/apk/release/app-release.apk | grep -E 'baseline.prof|lib/arm64-v8a'
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Release-only `NoSuchMethodError` on a DTO | R8 renamed a field read reflectively | keep the exact class plus annotation: `-keepclassmembers,allowobfuscation class ... { @Json <fields>; }` |
| Build fails with `Missing class ...` after adding a library | rules mention optional dependencies that are absent | add `-dontwarn` for that exact package only, never project-wide |
| Play rejects the upload: version code already used | `versionCode` derived per branch | one CI counter, monotonic per track; re-check with `bundletool dump manifest` |
| Baseline profile present but cold start is unchanged | profile generated from a debuggable variant, or not shipped | generate from the release variant and confirm `assets/dexopt/baseline.prof` in the APK |
| Bundle uploaded but Play reports a signature error | signed with a debug or wrong upload key | sign with the upload key; Play App Signing holds the distribution key |

## Verification

```bash
./gradlew :app:assembleRelease :app:bundleRelease
./gradlew -q :app:signingReport | grep -A2 'Variant: release'
bundletool dump manifest --bundle=app/build/outputs/bundle/release/app-release.aab --module=base \
  | grep -E 'targetSdkVersion|versionCode'
unzip -l app/build/outputs/apk/release/app-release.apk | grep baseline.prof
```

- `signingReport` shows the release variant on the release config, not `debug`.
- The manifest dump reports `targetSdkVersion` at or above the current Play floor
  and a `versionCode` higher than the last upload.
- The `unzip` line prints `assets/dexopt/baseline.prof`; absence means the profile
  was not packaged and startup pays for it on every install, and there is no
  `lib/arm64-v8a` entry in a build that skipped 64-bit libraries.

## Sources (2026)

- https://developer.android.com/topic/performance/app-optimization/keep-rules-overview
- https://developer.android.com/topic/performance/baselineprofiles/create-baselineprofile
- https://developer.android.com/google/play/requirements/target-sdk

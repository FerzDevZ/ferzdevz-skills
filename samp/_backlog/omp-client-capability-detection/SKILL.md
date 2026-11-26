---
name: omp-client-capability-detection
description: Detect open.mp, launcher and mobile clients safely.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, client, compat]
    category: samp
---

# Client capability detection

## When to Use

- A feature only works on some clients (voice, launcher encryption, custom models, UI size).
- You need to log which client population a server actually serves.

## 2026 Compatibility & Architecture Matrix

| Question | Native / signal | Since |
| --- | --- | --- |
| open.mp client, not legacy SA-MP | `IsPlayerUsingOmp(playerid)` | v1.4.0.2779 |
| Android SA-MP mobile client | `IsPlayerUsingAndroid(playerid)` (community include) | third-party |
| Launcher present | connection metadata / version string logged at connect | launcher v1.6.x |
| Custom-model support | 0.3.DL client only; open.mp custom models are server-side | — |

## Production Implementation

```pawn
enum ClientCaps {
    bool:capOmp,
    bool:capAndroid,
    bool:capVoice,     // Windows ASI only today
    bool:capBigUi      // phone screens need the compact HUD
}

new g_Caps[MAX_PLAYERS][ClientCaps];

public OnPlayerConnect(playerid)
{
    g_Caps[playerid][capOmp]     = IsPlayerUsingOmp(playerid);
    g_Caps[playerid][capAndroid] = IsPlayerUsingAndroid(playerid);
    g_Caps[playerid][capVoice]   = !g_Caps[playerid][capAndroid] && g_Caps[playerid][capOmp];
    g_Caps[playerid][capBigUi]   = !g_Caps[playerid][capAndroid];

    printf("client %d omp=%d android=%d", playerid,
        g_Caps[playerid][capOmp], g_Caps[playerid][capAndroid]);
    return 1;
}
```

Rules:

- Capabilities are decided **server-side at connect**; never accept a client-sent capability.
- Re-check after a reconnect: a player can switch client between sessions.
- Use caps to choose UI density and to hide unsupported features, not to grant permissions.

## Deprecated Traps & Edge Cases (2026)

- `IsPlayerUsingOmp` returns false for legacy SA-MP clients and for some launcher versions;
  treat false as "unknown", not "legacy".
- Feature flags and permissions are different things: an unsupported client must not lose
  access to gameplay, only to the unsupported presentation.
- Logging the raw client version string is PII-adjacent; log the derived flags instead.

## Verification

- Connect one open.mp client and one mobile client; the printed flags differ.
- With voice enabled, the mobile client never sees the voice button.
- `grep -rn "IsPlayerUsingOmp" qawno/include/` shows the native exists in your includes.

## Sources (2026)

- https://open.mp/docs/changelog (v1.4.0.2779)
- https://open.mp/docs/scripting/functions/IsPlayerUsingOmp
- https://github.com/Fairuz-Afdhal/IsPlayerUsingAndroid

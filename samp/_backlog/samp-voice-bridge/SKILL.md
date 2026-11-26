---
name: samp-voice-bridge
description: Add voice chat to a server without breaking mobile.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, voice, audio]
    category: samp
---

# Voice chat bridge

## When to Use

- Adding proximity or radio voice to an open.mp / SA-MP 0.3.7 R5 server.
- A voice channel leaks after disconnect, or players hear the wrong interior.

## 2026 Compatibility & Architecture Matrix

| Piece | 2026 state |
| --- | --- |
| Server | omp-voice (VoiceChat v2): open.mp component, SA-MP 0.3.7 R5 plugin bridge |
| Client | Windows `.asi` only (needs an ASI loader such as SilentPatch/CLEO) |
| Transport | relay process + UDP audio port (default 7779, overridable in `voice.ini`) |
| Crypto | token minted per player, bound to IP, AEAD-encrypted audio |
| Android / mobile SA-MP clients | **not supported** by the Windows ASI client |

## Production Implementation

1. Drop the component into `components/` (open.mp) or `plugins/` (SA-MP), the include into
   `qawno/include/`, and `voice.ini` beside the server binary.
2. Enable it for legacy scripts in `config.json`:

```json
{ "legacy_plugins": ["VoiceChat"] }
```

3. Open the audio port for UDP. The relay and the audio port are separate; only the audio
   port must match the client config:

```bash
sudo ufw allow 7779/udp
```

4. Drive the lifecycle from the gamemode. These natives exist in `voicechat.inc` (v2):

```pawn
public OnPlayerConnect(playerid)
{
    new ip[16];
    GetPlayerIp(playerid, ip, sizeof ip);
    Voice_OnPlayerConnect(playerid, ip);   // mint token, bind IP
    return 1;
}

public OnPlayerDisconnect(playerid, reason)
{
    Voice_OnPlayerDisconnect(playerid);    // leave channels, free token
    return 1;
}
```

5. Build gameplay on channels, not on a voice "mode" switch:

```pawn
new g_Radio = INVALID_VOICE_CHANNEL; // store the handle you get from Voice_CreateChannel

// per faction
Voice_CreateChannel("pd_radio");
Voice_AddToChannel(playerid, g_Radio);
Voice_SetChannelFilter(g_Radio, VOICE_FILTER_RADIO);
Voice_SetPlayerRange(playerid, 25.0);
```

6. Position updates must follow the player, not the tick:

```pawn
public OnPlayerUpdate(playerid)
{
    static last[MAX_PLAYERS];
    if (GetTickCount() - last[playerid] < 200) return 1;  // 5 Hz is enough for voice
    last[playerid] = GetTickCount();
    new Float:x, Float:y, Float:z;
    GetPlayerPos(playerid, x, y, z);
    Voice_UpdatePosition(playerid, x, y, z);
    return 1;
}
```

7. Gate the feature by client type before showing any voice UI (see
   `omp-client-capability-detection`).

## Deprecated Traps & Edge Cases (2026)

- Shipping voice to Android players: the client is a Windows ASI; mobile clients cannot
  load it, so a "join voice" button must be hidden by capability check.
- Forgetting `Voice_OnPlayerDisconnect` leaves ghost members and keeps the token alive.
- `Voice_SetPlayerRange` per tick causes audio jitter; set it on state change only.
- Interior/world gating is server-side policy: the relay does not know interiors.
- The audio port is UDP; opening only TCP produces "connected but silent".

## Verification

- `Voice_GetChannelCount()` returns the expected number after setup, and drops back after
  every player disconnects.
- Two clients in the same interior hear each other; one in another world does not.
- `sudo ss -lunp | grep 7779` shows the relay listening.
- Include check: `grep -c "native Voice_" qawno/include/voicechat.inc` matches the natives
  you call.

## Sources (2026)

- https://github.com/staark-dev/omp-voice
- https://github.com/staark-dev/omp-voice/blob/main/samp/include/voicechat.inc
- https://github.com/CyberMor/sampvoice

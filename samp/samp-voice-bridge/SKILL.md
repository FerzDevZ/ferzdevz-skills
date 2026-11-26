---
name: samp-voice-bridge
description: Use when adding proximity or radio voice to a server.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, voice, audio, relay]
    category: samp
---

# Bridge a voice relay into the gamemode

Voice is not a Pawn feature: it is a second process (`voice_relay`) plus a client DLL, with Pawn
only deciding who may be heard by whom. Keep that split and the integration is a lifecycle, a
position pump and a channel table. Forget it and you end up writing position updates at 60 Hz,
which is where audio jitter comes from.

## When to Use

- Adding proximity, radio or phone voice to an open.mp 1.6.x or SA-MP 0.3.7 R5 server.
- Players hear someone through a wall, across interiors, or after that player disconnected.
- Mobile players cannot hear anyone, or the voice UI shows up for clients that cannot load it.
- Choosing between a component, a legacy plugin and an external voice bot.

## Compatibility & Stack Matrix (2026)

| Piece | 2026 state | Note |
| --- | --- | --- |
| Server side | omp-voice VoiceChat v2 — open.mp component, SA-MP 0.3.7 R5 plugin | same `voicechat.inc` for both |
| Client | Windows `.asi` (DLL) | Android/mobile clients cannot load it |
| Relay | separate `voice_relay` process | plugin talks to it over loopback IPC |
| Audio port | 7779/UDP by default | the only port that must be open inbound |
| Command port | 7780 (server to client, token) | client side; may need forwarding on WAN |
| Config | `voice.ini` (server), `voicechat.ini` (client) | only `audio_port` must match |
| Crypto | per-connect token, IP-bound, AEAD audio | delivered server-side, never client-reported |
| Ranges | whisper ~8u, normal ~18u, shout ~40u | presets, overridable per player |

The client never reports its own position: `Voice_UpdatePosition` takes position, interior,
virtual world and vehicle state from the server, so a modified client cannot move its own voice
source (`pawn-raknet-packet-guard` covers the packet side).

## Production Implementation

1. Deploy three artifacts per platform — component (`components/`), relay binary beside the
   server, include into `pawno/include/` — and keep `voice.ini` next to the relay, not the
   server executable. Then open only the audio port: TCP instead of UDP is the classic
   "connected but silent" report, and an exposed control port lets strangers drive the relay.

```bash
cp build/voicechat.so /srv/omp/components/ && cp build/voice_relay /srv/omp/
sudo ufw allow 7779/udp && sudo ss -lunp | grep -E '7779|7778'
```

2. Create the proximity channel once at boot and keep the handle; `Voice_CreateChannel` takes
   the filter, whether the channel is positional, and a priority. Mint the session per player
   and free it on disconnect — the plugin needs the real IP so the token is delivered to that
   host and the relay's secondary IP check passes:

```pawn
new gProximity = -1;

public OnGameModeInit()
{
    gProximity = Voice_CreateChannel(VOICE_FILTER_NONE, true, 1);
    printf("[voice] proximity channel %d", gProximity);
    return 1;
}

public OnPlayerConnect(playerid)
{
    new ip[16];
    GetPlayerIp(playerid, ip, sizeof ip);
    Voice_OnPlayerConnect(playerid, ip);          // mint + deliver token + bind IP
    Voice_AddToChannel(playerid, gProximity);
    return 1;
}
```

`OnPlayerDisconnect` must call `Voice_OnPlayerDisconnect(playerid)` — it leaves every channel
and frees the token; skipping it leaves a ghost listener the relay keeps streaming to.

3. Pump position at 5 Hz, not per frame, and pass the authoritative world state. A closed
   vehicle is muffled, a bike or convertible is not — one boolean covers it well enough:

```pawn
public OnPlayerUpdate(playerid)
{
    static last[MAX_PLAYERS];
    if (GetTickCount() - last[playerid] < 200) return 1;
    last[playerid] = GetTickCount();

    new Float:x, Float:y, Float:z;
    GetPlayerPos(playerid, x, y, z);

    Voice_UpdatePosition(playerid, x, y, z,
        GetPlayerInterior(playerid), GetPlayerVirtualWorld(playerid),
        IsPlayerInAnyVehicle(playerid) ? VOICE_VEH_CLOSED : VOICE_ONFOOT);
    return 1;
}
```

4. Build gameplay out of channels, not out of a global "voice mode". A faction radio is one
   channel with the radio filter; membership changes on duty change, never per tick:

```pawn
new gPdRadio = -1;

stock RadioCreate()
{
    gPdRadio = Voice_CreateChannel(VOICE_FILTER_RADIO, false, 80);
    Voice_SetChannelFilter(gPdRadio, VOICE_FILTER_RADIO);   // bandpass, squelch, garble
}

stock RadioJoin(playerid)
{
    Voice_AddToChannel(playerid, gPdRadio);
    Voice_SetPlayerRange(playerid, VOICE_RANGE_NORMAL);
}

// on duty change: Voice_RemoveFromChannel(playerid, gPdRadio), guarded by Voice_IsInChannel
```

5. Drive push-to-talk from the plugin's callback rather than polling keys — the relay knows which
   bus the key belongs to, so `Voice_SetTransmitting(playerid, down, channelid)` in
   `OnPlayerRadioKey` is the whole implementation.

6. Gate the UI by client type — the client is a Windows `.asi`, so an Android player cannot load
   it; hide the "join voice" button after a capability check (`omp-client-capability-detection`).
   Tune ranges, falloff and the `speakerphone` flag in `voice.ini`, then apply live with
   `Voice_ReloadConfig()` from an admin command rather than a restart.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Connected but silent for everyone | only TCP opened, or mismatched `audio_port` | allow 7779/udp, match `audio_port` in both ini files |
| Ghost listener after reconnect | `Voice_OnPlayerDisconnect` never called | call it in `OnPlayerDisconnect` |
| Audible through interior walls | position sent without interior/world | pass `GetPlayerInterior` and `GetPlayerVirtualWorld` |
| Audio stutters in crowded areas | position sent per frame, ranges per tick | 200 ms pump, ranges on state change only |
| Mobile players see a dead voice button | UI not gated by client capability | hide it where the ASI cannot load |
| Radio channel grows forever | members added on spawn, never removed | remove on duty change and on disconnect |
| Relay dies with the server | started by hand, no supervisor | run it under systemd beside the server |
| Token rejected behind a proxy | client reached through another public IP | pass the observed IP, or `Voice_RegisterPlayerIp` |

## Verification

The relay must be listening on UDP only, with the control port on loopback, and the include you
compile against must expose the natives you call:

```bash
sudo ss -lunp | grep -E 'voice_relay|7779|7778'
grep -c '^native Voice_' qawno/include/voicechat.inc
```

Expected shape on a healthy host — one public UDP socket, one loopback socket, and the 21
natives of the v2 include:

```text
udp UNCONN 0 0 0.0.0.0:7779    users:(("voice_relay",pid=812,fd=7))
udp UNCONN 0 0 127.0.0.1:7778  users:(("voice_relay",pid=812,fd=8))
21
```

## Sources (2026)

- https://github.com/staark-dev/omp-voice — VoiceChat v2: relay layout, ports, `voice.ini` sections, server-authoritative positioning.
- https://github.com/staark-dev/omp-voice/blob/main/samp/include/voicechat.inc — exact native signatures, filter/range/mix constants, `OnPlayerRadioKey`.
- https://open.mp/docs/server/config.json — component loading and legacy plugin bridging next to a component.

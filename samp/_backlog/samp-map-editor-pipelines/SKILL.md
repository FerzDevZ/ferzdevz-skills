---
name: samp-map-editor-pipelines
description: Move map editor output into streamer code.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, mapping, streamer, tools]
    category: samp
---

# Map editor pipelines

## When to Use

- Output from Ultimate Creator, Fuse or Texture Studio must become server code.
- A converted map has missing collision, flicker, or objects that never appear.

## 2026 Compatibility & Architecture Matrix

| Tool | Output | Conversion note |
| --- | --- | --- |
| Ultimate Creator | `CreateObject` lines | convert to `CreateDynamicObject` |
| Fuse Map Editor V3 | `CreateObject` / `CreateDynamicObject` | already streamer-aware |
| Texture Studio | objects + materials | keep material index order |
| MapFix | filterscript, fixes stock map textures | load before your map, not after |

## Production Implementation

1. Convert every object, including the ones the editor emitted with `CreateObject`:

```bash
bin/samp-map-upgrade.js map.txt > map.streamer.pwn
```

2. Keep coordinates and material indices intact; only the function changes:

```pawn
CreateDynamicObject(modelid, x, y, z, rx, ry, rz, worldid, interiorid, playerid, streamdistance, drawdistance);
```

3. Preload the area for the player so the first seconds are not empty:

```pawn
Streamer_UpdateEx(playerid, x, y, z);
```

4. For texture-heavy maps, set distances deliberately: `streamdistance` controls when the
   object exists, `drawdistance` when it renders. A large gap produces pop-in.

## Deprecated Traps & Edge Cases (2026)

- `RemoveBuildingForPlayer` after objects stream in: the removal arrives too late and the
  original building stays for that session.
- 1000-removal limit per player: exceeding it silently drops the tail.
- Materials past index 15 on custom models are ignored by some editors' export.
- MapFix loaded after your map can undo your texture edits.

## Verification

- Object count in game (`CountDynamicObjects`) matches the exported file count.
- No pop-in when flying across the map at draw distance.
- Reconnect twice: removals and objects behave the same.

## Sources (2026)

- https://open.mp/docs/awesome
- https://github.com/Pottus/Texture-Studio
- https://github.com/fusez/Map-Editor-V3
- https://github.com/NexiusTailer/Ultimate-Creator
- https://github.com/NexiusTailer/MapFix

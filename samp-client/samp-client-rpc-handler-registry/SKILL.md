---
name: samp-client-rpc-handler-registry
description: Use when adding a client RPC handler without collisions.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, client, cpp, rpc, raknet, android]
    category: samp-client
---

# Adding an RPC handler to the client without breaking the table

Every feature that arrives from the server is an RPC: a numeric id, a bit stream, and one
registered function. The table is flat and global. A wrong id silently shadows another
feature, a missing `Read` guard reads garbage into the next field, and a handler that
allocates before validating leaves pools half-written when the packet is malformed.

## When to Use

- You are implementing a server feature whose RPC the client does not handle yet.
- An existing feature stopped working after someone added a handler.
- A custom RPC arrives on a different path (`Packet_CustomRPC`) and you need to know why
  registering it does not help.
- A handler crashes only when the server sends a truncated packet.
- Not for outgoing RPCs only (menu select, click): this is the receive table.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Client | samp-client-ferzdevz (C++/JNI, Android) | `samp/net/scriptrpc.cpp`, `samp/net/netgame.cpp` |
| RPC ids | 145 defined in `samp/vendor/raknet/SAMP/SAMPRPC.cpp` | official range is owned by that file |
| Registration | `RegisterAsRemoteProcedureCall(&RPC_ScrX, ScrX)` | 84 registrations today |
| Stream | `RakNet::BitStream bs(Data, (bits / 8) + 1, false)` | read-only, byte-rounded |
| Custom path | `Packet_CustomRPC` with `0x29`, `0x2A` | bypasses the registered table |
| Pools | `m_pPools->pVehiclePool`, `pPlayerPool`, `pMenuPool`, ... | mutate only after full parse |

## Production Implementation

1. Find a free id before writing code. The official table is a single C++ file; a
   hand-picked number that collides is the most expensive mistake here.

```bash
grep -c "^int RPC_" client/app/src/main/cpp/samp/vendor/raknet/SAMP/SAMPRPC.cpp   # 145
grep -n "RPC_ScrYourFeature" client/app/src/main/cpp/samp/vendor/raknet/SAMP/SAMPRPC.cpp
```

2. Declare the id next to the others, then the handler, then the registration. Three
   places, and a build that fails loudly if the handler signature is wrong.

```cpp
// vendor/raknet/SAMP/SAMPRPC.cpp — new id, checked against the 145 already there
int RPC_ScrYourFeature = 187;

// net/scriptrpc.cpp — declaration, definition, registration
void ScrYourFeature(RPCParameters* rpcParams);
pRakClient->RegisterAsRemoteProcedureCall(&RPC_ScrYourFeature, ScrYourFeature);
```

3. Parse defensively, in wire order, one `Read` at a time. Compare with the existing
   `ScrSetGravity` in this client, which reads once and never checks:

```cpp
// today: a truncated packet leaves fGravity uninitialised and still sets it
float fGravity;
RakNet::BitStream bsData(Data, (iBitLength / 8) + 1, false);
bsData.Read(fGravity);
pGame->SetGravity(fGravity);
```

```cpp
// the shape to copy for a new handler: guard every read, validate, then mutate
void ScrYourFeature(RPCParameters* rpcParams)
{
    if (!pNetGame || !pGame) return;
    unsigned char* Data = reinterpret_cast<unsigned char*>(rpcParams->input);
    RakNet::BitStream bs(Data, (rpcParams->numberOfBitsOfData / 8) + 1, false);

    uint8_t slot = 0;
    float value = 0.0f;
    if (!bs.Read(slot) || !bs.Read(value)) return;   // truncated packet
    if (slot >= MAX_PLAYERS) return;                 // out of range for the pool
    if (!std::isfinite(value)) return;               // NaN/Inf from a hostile packet

    pGame->SetGravity(value);                        // only now mutate
}
```

4. Validate ranges against the pool that will be touched, not against the packet's own
   claim. `MAX_MENUS`, `MAX_OBJECTS`, `MAX_PLAYERS` are the real limits.

5. Keep handlers idempotent. RakNet may deliver a reliable-sequenced packet twice after a
   reconnect; a handler that appends rows or spawns entities will double up.

6. Custom RPCs do not use the table. They arrive in `Packet_CustomRPC` and are switched by
   a small numeric id (`0x29`, `0x2A` in this client). Registering one there is a no-op, and
   both paths must be checked when a feature "does nothing".

```cpp
void CNetGame::Packet_CustomRPC(Packet *p)
{
    // switch on the custom id, then parse with the same Read-guard discipline
}
```

7. Log one line per handled RPC while bringing it up, then drop it to debug level. A
   count of calls is the fastest way to tell "not registered" from "registered but never
   invoked".

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Another feature breaks after adding a handler | id collision with an existing RPC | grep the id file; pick an unused number |
| Client crashes only on truncated packets | `Read` return value ignored | guard every read; return before touching pools |
| Handler runs but nothing changes | feature uses `Packet_CustomRPC`, not the table | check the custom switch, not the registration |
| Values leak between calls | reused static buffers | parse into locals, copy only validated data |
| Duplicate spawns after reconnect | non-idempotent handler | key the mutation on the server id |
| Works in debug, fails in release | uninitialised read on a short stream | zero-init locals, check every `Read` |
| Handler never fires | registered before the client joined, or wrong function pointer | register in the same block as the working neighbours |

## Verification

```bash
# every id is defined exactly once
grep -o "^int RPC_[A-Za-z]*" client/app/src/main/cpp/samp/vendor/raknet/SAMP/SAMPRPC.cpp \
  | sort | uniq -d        # must print nothing

# your handler is registered exactly once
grep -c "RegisterAsRemoteProcedureCall(&RPC_ScrSetWeatherRegion" \
  client/app/src/main/cpp/samp/net/scriptrpc.cpp    # 1

# runtime proof that the packet arrived
adb logcat -s samp | grep -i "weather region"
```

A handler that is registered but never logs means the server is not sending it; a handler
that logs garbage means a `Read` guard is missing.

## Sources (2026)

- https://open.mp/docs/scripting/functions/SetGravity
- https://github.com/openmultiplayer/omp-stdlib

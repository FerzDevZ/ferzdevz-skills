---
name: samp-client-object-entity-lifecycle
description: Use when CreateObject RPC arrives but objects never draw.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, client, cpp, objects, rendering, android]
    category: samp-client
---

# Server object -> engine entity: the whole loop

A client object pool can look correct and draw nothing: ids, positions and rotations live
in your own array while `m_pEntity` stays null. Everything visible in game comes from one
engine call, and everything the server sends afterwards (`MoveObject`, `SetObjectRot`,
`DestroyObject`) addresses that engine id, not your pool slot.

## When to Use

- Server objects arrive (`RPC_ScrCreateObject`) but nothing appears in the world.
- `MoveObject` runs without error and the object never moves.
- Objects appear for a second, then vanish after a stream-out/in cycle.
- You are adding a new object-like entity (pickup, actor, attached object) and need the
  same create/destroy contract.
- Not for draw-distance or LOD tuning: that is streamer work on the server.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Client | samp-client-ferzdevz (C++/JNI, Android) | `client/app/src/main/cpp/samp/` |
| Engine access | `ScriptCommand(&create_object, ...)` | returns an engine pool index, not a pointer |
| Streaming | `CStreaming::TryLoadModel` | call before create; a failed load leaves no entity |
| Pool lookup | `GamePool_Object_GetAt(id)` | returns `CPhysical*`, may be null on failure |
| Pool cap | `MAX_OBJECTS` | server ids outside the pool must be rejected, not clamped |
| RPC | `RPC_ScrCreateObject` | carries the server-side object id |

## Production Implementation

1. Validate the server id before touching anything. A server may send an id that has no
   slot on this client; clamping it silently corrupts a neighbouring object.

```cpp
bool CObjectPool::New(OBJECTID ObjectID, int iModel, CVector vecPos, CVector vecRot, float fDrawDistance)
{
    if (!samp::validId(ObjectID, MAX_OBJECTS)) return false;
    if (m_pObjects[ObjectID] != nullptr) Delete(ObjectID);   // reuse must destroy first
    m_pObjects[ObjectID] = pGame->NewObject(iModel, vecPos, vecRot, fDrawDistance);
    if (m_pObjects[ObjectID] == nullptr) return false;
    m_bObjectSlotState[ObjectID] = true;
    return true;
}
```

2. Load the model, then create the engine object, then place it. Three separate failures:
   model missing, create refused, entity not in the game pool.

```cpp
if (CStreaming::TryLoadModel(iModel))
{
    ScriptCommand(&create_object, iModel, vecPos.x, vecPos.y, vecPos.z, &m_dwGTAId);
    CPhysical* pEntity = GamePool_Object_GetAt(m_dwGTAId);
    if (pEntity)
    {
        m_pEntity = pEntity;
        if (vecRot.x != 0.0f || vecRot.y != 0.0f || vecRot.z != 0.0f)
            ScriptCommand(&set_object_rotation, m_dwGTAId, vecRot.x, vecRot.y, vecRot.z);
        pEntity->SetPosn(vecPos);
        pEntity->Add();          // without Add the entity exists but is never drawn
    }
}
```

3. Keep the engine id (`m_dwGTAId`) as the only handle used by later RPCs. Pool slots are
   yours; engine ids are the game's. Storing one where the other is expected is the most
   common source of "moves on the server, frozen on screen".

4. Destroy in this order: engine object, then materials, then the wrapper.

```cpp
CObject::~CObject()
{
    if (m_pEntity && GamePool_Object_GetAt(m_dwGTAId))
        ScriptCommand(&destroy_object, m_dwGTAId);
    m_pEntity = nullptr;
    m_dwGTAId = 0;
    // 16 material slots: RwTextureDestroy + delete[] text, otherwise the next object
    // that reuses the slot inherits a freed texture pointer.
}
```

5. Log one line per create and per failure, with both ids. That line is the difference
   between "the server is wrong" and "the model never loaded".

```cpp
Log("CObject: id=%d model=%d gta=%u entity=%p", ObjectID, iModel, m_dwGTAId, (void*)m_pEntity);
```

6. On reconnect or mode change, reset the pool through one path. A pool whose entities
   survived a disconnect leaks engine objects and the ids never come back.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Object never appears, no log | `m_pEntity` null and nobody checked | log create result; check `TryLoadModel` return |
| Appears then vanishes | entity created, `Add()` never called | call `Add()` after `SetPosn` |
| `MoveObject` accepted, object frozen | later RPC used the pool slot instead of `m_dwGTAId` | store and use the engine id |
| Second object at same server id is invisible | old wrapper deleted without `destroy_object` | destroy the engine object in the destructor |
| Crash after many object cycles | material textures freed twice or never | release all 16 slots in one destructor pass |
| Neighbouring object changes position | out-of-range server id clamped into a valid slot | reject ids >= `MAX_OBJECTS` |
| Wrong rotation at spawn | `set_object_rotation` skipped when any component is 0 | check all three components, not just one |

## Verification

```bash
# the create/destroy pair exists and is reachable from the pool
grep -n "create_object\|destroy_object" client/app/src/main/cpp/samp/game/object.cpp

# the pool rejects foreign ids and destroys before reuse
grep -n "validId\|Delete(ObjectID)" client/app/src/main/cpp/samp/net/objectpool.cpp

# runtime evidence: one line per created object, entity pointer non-null
adb logcat -s samp | grep "CObject:"
```

A create log with `entity=0x0` means the model loaded but the engine refused the spawn —
check the id, not the RPC parser.

## Sources (2026)

- https://open.mp/docs/scripting/functions/CreateObject
- https://open.mp/docs/scripting/functions/DestroyObject

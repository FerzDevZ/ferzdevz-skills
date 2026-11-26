id: destroys-on-disconnect
weight: 2
path: hud-fixed.pwn
must_match: PlayerTextDrawDestroy|TextDrawDestroy
note: elements must be released, otherwise the pool leaks across sessions

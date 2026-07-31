# Master Architecture

The orchestration manifest is the registry authority. `FRONTS.md` is its
deterministic pending-state projection. Registered front paths stay relative to
this root.

All registry, reflection, record, and closeout changes use the same journaled
transaction engine.

# Frontend module boundaries

The frontend keeps Vue's existing reactive state model. `store.js` is the
composition root, not a feature implementation module.

## Dependency direction

1. `api/` owns HTTP and stream transport details plus response normalization.
2. `app/` owns authentication, bootstrap, global status, and application-level
   lifecycle transitions.
3. `features/<feature>/` owns one feature's state transitions and resources.
4. `ui/` adapts feature actions to Vue components such as modal content.
5. `store.js` wires these modules together and exposes the compatibility API
   consumed by existing Vue components.

Feature modules must not import `store.js` or Vue components. Dependencies are
passed into their factory functions so modules remain independently testable.

## Resource ownership

- The editor module serializes Blockly saves and invalidates stale operations
  whenever the active document changes.
- The runtime stream module owns EventSource instances and reconnect timers.
- The device module owns preview timers and stops them when previews, sessions,
  or authentication end.
- The app module owns authentication generations and clears feature resources
  when a session expires or the user logs out.

New behavior should be added to the owning module. Add code to `store.js` only
when a new dependency must be composed or a compatibility export is required.

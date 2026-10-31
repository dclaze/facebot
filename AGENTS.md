# Facebot collaboration

Doug requires a dedicated Git worktree and branch for every implementation session.
Do not implement in the shared main checkout or share another session's Git index.
Before editing, run git worktree list and create/select your session worktree.
Preserve other owners' changes; exchange reviewed commits and cherry-pick them.
Do not copy ongoing working-tree changes over another owner's files.

The canonical coordination handoff remains /Users/mv_server/Development/facebot/STATUS.md.
Read its current ownership/reload notices before runtime changes. Append-only coordination
entries there are the sole shared-file exception; implementation and tests stay in your tree.
Never stage private .local assets, recordings, pairing data, credentials or device identifiers.
A shared ignored .local asset link may be used for authorized runtime verification;
never mutate other owners' assets or run competing app installs/server reloads.
Runtime deployment has one named owner at a time; worktree isolation does not authorize
competing live processes. Record tree, branch, exact commit and evidence at handoff.

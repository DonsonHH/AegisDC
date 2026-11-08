# Remote computation and evidence retention

User requirement confirmed 2026-11-09. This governs infrastructure and artifact placement; scientific protocols, budgets, original failures and acceptance gates remain unchanged.

## Execution

1. Use the installed `use-renly-slurm` skill for cluster access, staging, environment preparation, job submission, monitoring and retrieval. Use a host-key-verifying client and keep credentials out of project files and logs.
2. Before remote mutation, verify `renly`, `mu01` and `/share/home/renly`; inspect live partitions and `squeue -u renly`. Login-node work is limited to transfer, downloads, setup and lightweight inspection. Schedule training, inference, evaluation, simulation and heavy verification through Slurm with explicit resources.
3. Stage code, exact input/config identities, dependencies and model files before allocation. Compute nodes are offline. Reuse an appropriate verified environment or create an isolated environment on the login node; keep shared environments stable during jobs.
4. Preserve a unique job directory with source/config, stdout/stderr, environment and attempt/terminal records. A maintenance integrity job is not a research trial. Research attempts still require their own frozen protocol and budget.
5. Confirm Slurm state/exit code, artifact identity and readability. Detailed trajectories, datasets and checkpoints stay on the private server; return the required plots, tables, summaries and integrity receipts.
6. If remote access, scheduling or dependencies are unavailable, record the specific failure and retain local inputs. Continue independent editing and documentation where possible; local training/inference/evaluation is not an automatic fallback.

The existing research storage root is `/share/home/renly/renly-patrol-rsi`. Use a separate named directory for each activity. The 2026-11-09 cleanup retention namespace is `local-archives/20261109-cleanup-01`; preserve its manifest and verification receipt when local copies are released. Discover current capacity and topology rather than treating this document as a live snapshot.

## Local cleanup

1. Check the current mainline/ticket, Git state, active chats/agents/process references and the exact authorized paths. Keep both the canonical main checkout and the active chat's working directory.
2. Preserve uncommitted or unpushed source, unique inputs, conclusions, original failures, protocols and required replication evidence. Record uncertain artifacts as retained. The current canonical evidence tree is not a disposable duplicate merely because it also exists in Git history.
3. Confirm duplicate historical worktree heads are included in the published branch. Inspect ignored files separately; a clean Git status does not prove ignored data are disposable.
4. For local-only data/checkpoints that need retention, transfer directly to private storage without creating another full C-drive backup. Keep a path/size/hash index. Release the local copy only after complete remote identity and readable-format checks; preserve failures and partial transfers.
5. Remove old worktrees using `git worktree remove` without force. Keep branches and Git history. Validate resolved absolute deletion targets stay in the authorized Renly roots and exclude the current directories; preserve any new or uncertain change.
6. Reinstallable dependencies and runtime caches are separate from durable evidence. Preserve version metadata and verify there are no project edits or unique data before removing an installation cache. Keep canonical summaries/figures and small source changes available locally.
7. Report target categories, deleted logical bytes, actual disk availability, retention locations/reasons and the checks showing that the current task can continue. Preserve source/record identities rather than rewriting old manifests to make a moved artifact appear to have stayed local.

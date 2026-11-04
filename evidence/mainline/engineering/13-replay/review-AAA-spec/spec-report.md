# Spec review: ticket 13 private functional replay

Baseline: `08f2c1bc5dcf756ab6a7766a4f545f29f788ddb4`.
Reviewed candidate: `aaa4d8cba3738e47e700c2134000a72bd2390cc0`.
Known-v1 execution/delivery: `264e8423` / `3e23431f`.
Scope: replay contracts, shared time/inventory integration and saved evidence. Numerical ticket 12 remains unaccepted/NO-GO under refinement.

## Spec

**Findings: 1 open; closed: 0.** One reader-authority defect groups the unsupported-version, structure and terminal-state cases; these are not separate physical-model bugs.

The contract states "Lifecycle is STARTED then COMPLETED or FAILED" and an absent terminal envelope is "UNFINALIZED_RUNNING_OR_INTERRUPTED" (13-replay-contract.md:87–94). Yet `replay.py:222/231` reads terminal/declaration objects without validating their schema or the terminal-status enumeration. In source-guarded temporary copies, changing only terminal schema to v999 still returns COMPLETED with a trajectory; a coherently rehashed unknown declaration version also passes; an arbitrary terminal state is returned. At `replay.py:216/219`, a valid declaration interrupted before lifecycle creation raises FileNotFoundError instead of the stated unknown state. A lifecycle containing exact bytes `42\n` causes uncaught AttributeError in `replay_attempt` (`:275`), with no finalized FAILED replay-request record. Originals were untouched and no plant executed. Validate typed/versioned headers and legal terminal states, handle incomplete setup distinctly from malformed origin, and preserve the request-level refusal lifecycle. Closure requires these exact probes to refuse/retain correctly.

Other reviewed behavior is coherent: commands cannot rewrite offered demand/weather/fault plans; canonical origins, bounded fixed-epoch coincidence, anchored PLC, explicit-empty/compensated floor accounting and recorded raw/applied times remain distinct. Exact replay recomputes the plant instead of feeding a saved truth path. Private future plans create no dispatch evidence; registered research remains closed behind ticket 30.

One read-only saved-delivery check passes 142 artifacts plus receipt, 93 source/tools, 139 retained failed-capture originals, two exact semantic pairs, thirteen terminal requests (six completed/seven failed) and one explicit retry. Stored command comparison retains demand 2 each but delivery 2 versus 1 through real flow/control differences. The legacy-check adapter derives expected exogenous/command/job inputs from the frozen prior case; neither actual outputs nor prior literals/checker are rewritten. Capture-01 remains failed with zero full runs; the later recorded full check is 330/328 with two disclosed optional skips.

Copy-only red probes and saved readback are in `C:/Users/Donson/AppData/Local/Temp/aegisdc-review-13-spec-attachments/`. No new simulation or suite ran. Functional replay/data success cannot establish ticket-12 numerical qualification, M2 completion, field calibration or research/AI gain.

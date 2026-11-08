# Narrow pre36 delivery-format review

**PASS** at `f1b1e19112330e82ff2d987a1ab58df0374c1cc9`:123 static/saved byte checks, zero project calls.

All five corrected Git ZIP blobs match the original, unchanged delivery-manifest SHA256 and size. Their84 members match both the sealed member hashes and the original local reviewer files; the original review manifests remain intact. The standalone matrix matches its original reviewer bytes and hash. The refused commit's differing ZIP/matrix bytes are exactly the originals with CRLF pairs normalized to LF.

The two precise `.gitattributes` exceptions follow the broad docs text rule. No runtime, config, test, exporter or verifier changed. The original delivery manifest is byte-identical, and no hash mismatch is waived. The actual first fresh-check refusal at `9b14d147` remains recorded with exit1 and the original assertion log.

The first reviewer script expected a generic FAIL label; the original receipt correctly says REFUSED_DELIVERY. That reviewer-only assertion error and its source are preserved; the second script checks the exact original status/source/exit code. No project, export, model or capture was rerun.

This review covers only byte-preserving delivery repair. Root's separate fresh verification of the complete54-file declaration remains its own delivery gate.

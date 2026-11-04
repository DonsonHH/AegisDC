# Spec and physical-source review: mainline ticket 10

Baseline: `1ec2503d6c88d5f4a31088777886977d9920bc23`.
Initial candidate: `dca40ac97c0e1c1d9a8eb101dadaeaabf174edca`.
Final reviewed/tested source: `efb7bbdc1d9140d8686cc28ad6ab998d0bb22321`.
Contracts: ticket 10, specification, MAINLINE, ADR0003 and the revised reserve implementation declaration.

## Spec

**Author-discovered finding: 1; verified closed: 1; remaining: 0.** No additional substantive Spec defect was established.

The ticket requires reserves to affect the facility "按容量和切换逻辑". At 25,310 W AC, a paid selector command removed intake demand but initially left UPS waiting against obsolete demand. The real author red is retained. `7e9015c0` adds bounded same-instant autonomous reserve settlement (`plant.py:620`), without a second PLC sample; nonconvergence fails explicitly. The final reverse-direction test also proves that restoring primary/intake demand starts UPS waiting at the actual 3 s paid sample, connects at 3.2 s and supplies 16,428.5714286 W, consistently for maximum steps 1/.25 s.

Finite UPS internal-control/converter energy, separately funded generator control/cranking and fuel, start/connection delays, depletion precedence, shared distribution, maintenance and fresh-delay recovery are explicit. Fan power has no UPS path. Primary/reserve removal uses one actual internal throughflow; signed capped sensible transfer and fan/actor heat have single boundaries. The hot-inlet/cold-storage pairing retains the accepted advection equation. Actual leakage, floor mixing, protection latching and post-control room access remain intact.

The [CSCEC procurement source](https://www.cscec.com.cn/xwzx_new/zqydt_new/202508/3897038.html) supports the equipment categories; the [LBNL v13 documentation](https://simulationresearch.lbl.gov/modelica/releases/v13.0.0/help/Buildings_Fluid_HeatExchangers.html) distinguishes sensible NTU from moisture models. The implementation preserves that source boundary and explicitly labels synthetic interfaces/settings.

Final verification: 26 focused tests pass with zero skips. Eighteen protected source/test/input files match the frozen Git blobs before and after tests and the independent whole-run probe. For 12.5 kJ UPS, 50 W control, .125 s transfer and 1 kW/.8 protected output, the hand prediction is exhaustion at 2025/208 s; 9,610.576923 J output +486.778846 J control +2,402.644231 J loss closes exactly and matches the run.

Guarded logs/receipt are in `aegisdc-review-10-spec-attachments/guarded-efb7bbdc-01/`; its reproducible script is in the parent attachment directory. Earlier unsealed observations remain separately labeled. No full suite, repository edit or registered research ran. Final saved-run/portable delivery and M1/root acceptance remain separate gates.

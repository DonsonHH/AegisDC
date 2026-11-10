# 53手算说明更正：密度998kg/m³

Independent Spec finding **39C-COMPOSITE-SPEC-10 (P3)**: the original frozen contract says density1000kg/m3 while also requiring unchanged51physics. The frozen51/53 scenario actually declares `water_density=998kg/m3`. The plant and completed53 result consistently used998; do not change physical input to match prose.

Retain the original contract and its red/green source blobs unchanged. This addendum corrects only that narrative parameter. At the declared full-speed operating point, Q=sqrt(150000/(4×12000000+3000000))m3/s and mass flow=998×Q≈54.124149225754714kg/s. The actual initial private scalar equals54.124149225754714 and matches the actual fixed public sample observed0/arrived0.5. Both remain below the unchanged99.7kg/s threshold.

No evaluator/plant code, test, input, classification, expected closure/cost/timing, attempt directory or invocation changes. Preserve red71 and green72, bind their actual original contract rather than pretending this later correction was executed then. New facility/model/research calls0. The [exact identity correction](evidence/39c-composite-density-correction-53.json) pins the original contract/input/output and execution revision.

This is a synthetic engineering parameter correction, not site calibration. Subsequent joint qualifications must retain998 and the original physical rules; whole39c still awaits remaining qualifications, recorded replay and full acceptance.

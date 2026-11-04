# Observed public-interface red/green slices

Source implementation: `37432b25a994c1c4e37d6747e9e9228a9ea3a44a`.
Each new slice was run with the primary interpreter, explicit worktree `PYTHONPATH`
and `python -X utf8 -m unittest discover -s tests -p test_full_facility_plant.py -v`.
The final result is 21/21 executed, zero failures/errors/skips. Raw red observations
are in the session tool transcript; old implementations were not restored to
manufacture a retrospective failure log.

|Slice|Observed red|Green behavior / independent reference|
|---|---|---|
|Fixed-volume property boundary|`ModuleNotFoundError: aegis_dc.thermodynamics`|External-EOS M=10 kg, U=2581678.41571952 J, V=.03323720367146753 m3 gives .8 MPa, 304.4774631633 K, x=.1 within declared interpolation tolerance|
|Runnable input|V2 file absent, then v1 exact-field contract rejected runtime|Backward-compatible v2 with all eight domains, SI/provenance records and explicit runtime topology|
|Paid pump boundary|`ModuleNotFoundError: aegis_dc.heat_transfer`|100 kPa, .01 m3/s, eta .5 gives 1 kW hydraulic /2 kW electrical; K times four halves q|
|Plate HX boundary|Missing `counterflow_exchange` import|Ch=4/Cc=8 kW/K, epsilon=.5, 320/300 K gives 40 kW and 310/305 K outlets|
|Full facility|`ModuleNotFoundError: aegis_dc.plant`|The same eight-domain scenario runs at the coupled derived steady point with component/whole-facility accounts|
|Timed supply loss|`Scheduled inputs are not yet implemented`, then zero grid outside inherited v1 range|Explicit v2 available-grid domain includes zero; .25 s outage splits the step, retains demand, produces 1.75 s deficit over 2 s, and stored solid heat persists|
|UPS independent account|Missing `ups_output_energy_J` summary key|Existing discharge dynamics exposed/audited: 3.6 MJ, eta .9, 100 kW exhausts at 32.4 s, 3.24 MJ output /.36 MJ loss; no negative reserve|
|Finite engineering work|`Scheduled work is not yet implemented`|120 s route +30 s work complete at exactly 150.25 s for a .25 s request; resources held/released|
|Pending work lifecycle|Missing `scheduled_arrival_at_s`; future arrival had been stored as actual|Planned and actual arrival/completion are separate; transit position follows worker and carried tool|
|Drainage/access crossing|Post-crossing job's accepted assertion failed|Downward crossing opens access at the declared event; empty event prevents negative water inventory|
|CLI run artifact|Argparse `invalid choice: simulate`|Compact stdout plus new-directory config/private-trace/balance/manifest artifacts; existing output refused|
|Property endpoints|A mathematically valid table-endpoint inversion called `at_pressure` one ulp out of range|Only exponentiation coordinate roundoff inside a valid segment is corrected; physical out-of-domain states/quality remain refused|
|Floor-water boundary account|Missing `floor_water_inlet_mass_kg` summary key|Inlet and drain mass/energy separately reported; 20 kg drain at 293.15 K /4180 J/(kg K) exports 24507340 J|
|Initial access-threshold direction|Initial equality plus draining kept access closed; accepted assertion failed|An initial threshold state draining toward the open side handles that zero-time crossing explicitly|

Already-green guards were retained and extended without being called new red
results: nonfinite/range validation, the other 24 external-EOS flash references,
out-of-domain flash failure, actual-power service/thermal response,
generator delay/fuel, shared-tool/qualification/worker/access refusal, no default
patrol, deterministic replay/no input mutation, and excessive-step rejection.
The analytic 3 K thermal rise, 100/95/5 kW conversion and joint service's 4 s deficit
are independent literal references, not copies of simulator expressions.

Final complete acceptance is recorded separately: 176 discovered, 174 executed,
zero failures/errors, two precisely identified pre-existing optional Torch skips,
zero unexpected skips, 20 saved original-file hashes verified. This is engineering
verification; no scientific gain, field validity or completed overall goal follows.

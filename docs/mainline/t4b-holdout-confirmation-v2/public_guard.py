"""Zero-facility information-wall check using registered, previously disclosed twins."""
from copy import deepcopy
import os

from context_t4b import ACT, bundle_inventory, check_runtime, check_sources, digest, read_inputs, require, slurm_id, write
from frozen_worker import FrozenWorker
from aegis_cost_baseline.rule import operative_view
from isolation import history
from isolation_guard import history_frames


def twins(role, bundle, world_a, world_b, folder):
    workers = [FrozenWorker(role, bundle, folder/(role+"-"+side+".stderr")) for side in ("a", "b")]
    try:
        for worker, dataset in zip(workers, (world_a, world_b), strict=True):
            worker.start(dataset[0])
        count = 0
        for a, b in zip(history_frames(world_a[1], 600), history_frames(world_b[1], 600), strict=True):
            one, two = [w.choose(world_a[0], frame, role, {}) for w, frame in zip(workers, (a, b), strict=True)]
            require(one == two, "same public frame must produce the same full response")
            count += 1
        require(count == 61, "complete shared clock")
        return dict(frames=count, worker_transcript=digest(workers[0].ipc), bundle=bundle[0])
    finally:
        for worker in workers:
            worker.close()


def guards(role, bundle, world, folder):
    results = []
    for guard in ("private_payload", "future_arrival"):
        p = FrozenWorker(role, bundle, folder/(role+"-"+guard+".stderr"))
        frame = deepcopy(world[1][0])
        if role == "B_COST":
            frame = operative_view(frame)
        if guard == "private_payload":
            frame["private_test_field"] = True
        else:
            frame["records"][0]["arrived"] = frame["time"]+60
        try:
            p.start(world[0])
            accepted = True
            try:
                p.message({"view": frame})
            except RuntimeError:
                accepted = False
        finally:
            p.close(failed=True)
        require(not accepted, "reject out-of-scope input")
        results.append(guard)
    return results


def main():
    _, plan = check_sources()
    check_runtime()
    inputs = read_inputs(plan)
    require(not any((ACT/"jobs").glob("*/a*/positions/*/*/native-entry.json")), "witness before facility")
    roots = bundle_inventory(plan, check_bytes=True)
    require(set(roots) == set(plan["panel"]["role_order"])-{"ORACLE"}, "all public roles")
    a, b = (history(key) for key in ("5-04", "5-10"))
    require(a[:2] == b[:2] and a[2] != b[2], "disclosed twins have equal public history and distinct latent causes")
    out = ACT/"isolation"
    out.mkdir()
    records = {role: twins(role, item, a, b, out) for role, item in roots.items()}
    negatives = {r: guards(r, roots[r], a, out) for r in ("B_COST", "V_COST", "V_COST_NOPROBE")}
    write(out/"result.json", dict(job=slurm_id(), author_job=inputs["author_job"], raw_development_pair=[a[3], b[3]],
        public_config=digest(a[0]), witness=records, rejection_guards=negatives, facility_entries=0,
        condition_sha256=os.environ["T4B_CONDITION_SHA"]))
    print("public twins", len(records), "x 61, six negative guards, zero facility entries", flush=True)


if __name__ == "__main__":
    main()

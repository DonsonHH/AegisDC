"""Line-oriented T11 dispatch. Each process is bound to one public role and position."""
import json
from pathlib import Path
import sys
import time


OAT = {
    "lambda_low": ("versions.V3", 0.5), "lambda_high": ("versions.V3", 2.0),
    "kappa_low": ("fee_in_person_seconds", 15), "kappa_high": ("fee_in_person_seconds", 60),
    "match_low": ("fixed_match_probability", 0.85), "match_high": ("fixed_match_probability", 0.99),
    "unknown_low": ("unknown_report_probability", 1 / 64),
    "unknown_high": ("unknown_report_probability", 1 / 16),
}
TREE_COUNTS = ("tree_ns", "leaf_ns", "tree_steps", "leaf_evaluations", "simulations", "nodes", "max_depth")


def configuration(bundle, role):
    if role not in ("POMCP", "MYOPIC") and role not in OAT:
        raise ValueError("Unregistered T11 public role")
    settings = json.loads((bundle / "aegis_risk_dispatch/settings.json").read_bytes())
    rules = json.loads((bundle / "aegis_action_cost/rules.json").read_bytes())
    center = (settings["versions"]["V3"], settings["fee_in_person_seconds"],
              settings["fixed_match_probability"], settings["unknown_report_probability"])
    if center != (1, 30, 0.95, 1 / 32):
        raise ValueError("Unexpected V_COST center")
    settings["maintenance_capacity"] = rules["bypass_capacity"]
    if role in OAT:
        parameter, value = OAT[role]
        if parameter == "versions.V3":
            settings["versions"]["V3"] = value
        else:
            settings[parameter] = value
    return settings, rules


def preload_random():
    # The original worker used -S. If requested, allow the frozen interpreter's
    # own installed NumPy before the public audit boundary, including venv layouts.
    if sys.flags.no_site:
        import sysconfig
        env_site = (Path(sys.executable).parent.parent / "lib"
                    / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages")
        for directory in (env_site, Path(sysconfig.get_path("purelib")), Path(sysconfig.get_path("platlib"))):
            if str(directory) not in sys.path and directory.is_dir():
                sys.path.append(str(directory))
    from numpy.random import Generator, PCG64
    Generator(PCG64(0)).random()


def lock_interface(event, args):
    if (event.startswith(("open", "os.", "socket.", "subprocess.", "ctypes.", "sys._getframe",
                          "sys.settrace", "sys.setprofile"))
            or event in ("import", "compile", "exec", "marshal.loads", "sys.addaudithook",
                         "gc.get_objects", "gc.get_referrers")):
        raise PermissionError("Closed public decision interface: " + event)


def main():
    if len(sys.argv) != 2 or not sys.flags.isolated:
        raise ValueError("Use isolated Python with one registered role")
    role = sys.argv[1]
    bundle = Path(__file__).resolve().parent
    sys.path.insert(0, str(bundle))
    settings, rules = configuration(bundle, role)
    import baselines
    from aegis_dc.joint_resources import transit
    from aegis_risk_dispatch import knowledge, policy
    from aegis_action_cost import planning
    from aegis_action_cost.permit import Gate

    gate = Gate(rules["exclusive_recovery_s"])
    tree_state = {}
    if role == "POMCP":
        preload_random()
        import pomcp

        def choose(*args):
            request, denied, branches, first, metrics = pomcp.search(*args)
            tree_state.update({field: metrics[field] for field in TREE_COUNTS})
            tree_state["effective_choices"] = len(branches)
            return request, denied, branches, first

        policy.choose_first = choose
    else:
        policy.choose_first = baselines.myopic if role == "MYOPIC" else planning.choose_first
    for architecture in ("ordinary", "power_board", "cooling_board"):
        knowledge.catalogue(architecture)
    module_names = ["baselines", "common", "public_work", transit.__module__]
    if role == "POMCP":
        module_names.append("pomcp")
    module_names.extend(name for name in sys.modules if name.startswith(("aegis_dc.", "aegis_action_cost.",
                                                                         "aegis_risk_dispatch.")))
    if any(not Path(sys.modules[name].__file__).resolve().is_relative_to(bundle) for name in module_names):
        raise RuntimeError("Public policy import outside the verified bundle")
    prohibited = {"native_v3", "plant_cost", "inputs_v3", "bounds", "score_saved", "aegis_dc.plant"}
    if prohibited.intersection(sys.modules):
        raise RuntimeError("Private module in the dispatch process")
    sys.addaudithook(lock_interface)
    pub = None
    for line in sys.stdin:
        message = json.loads(line)
        if set(message) == {"public"} and pub is None:
            pub = message["public"]
            if set(pub) != policy.PUB_FIELDS:
                raise ValueError("Unexpected static public fields")
            answer = {"ready": True, "role": role}
        elif set(message) == {"view"} and pub is not None:
            tree_state.clear()
            cpu_before = time.process_time_ns()
            wall_before = time.monotonic_ns()
            decision = policy.decide("V3", pub, message["view"], settings, gate)
            wall_ns = time.monotonic_ns() - wall_before
            cpu_ns = time.process_time_ns() - cpu_before
            timing = {name: 0 for name in TREE_COUNTS}
            timing.update(effective_choices=0, worker_wall_ns=wall_ns, worker_cpu_ns=cpu_ns,
                          reason=decision["rationale"]["reason"])
            timing.update(tree_state)
            answer = {"decision": decision, "timing": timing}
        elif message == {"close": True}:
            return
        else:
            raise ValueError("Unexpected public payload or order")
        print(json.dumps(answer, sort_keys=True, separators=(",", ":"), allow_nan=False), flush=True)


if __name__ == "__main__":
    main()

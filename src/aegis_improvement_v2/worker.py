"""An isolated interpreter for one static v2 descriptor, using public IPC only."""
import json
from pathlib import Path
import sys


def main():
    directory = Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(directory))
    import aegis_dc.joint_resources
    from aegis_risk_dispatch import knowledge
    from aegis_improvement_v2.policy import Policy

    space = json.loads((directory/"space.json").read_bytes())
    settings = json.loads((directory/"aegis_risk_dispatch/settings.json").read_bytes())
    settings["maintenance_capacity"] = 0.5
    for architecture in ("ordinary","power_board","cooling_board"):
        knowledge.catalogue(architecture)

    def deny(event, args):
        if event.startswith(("open","os.","socket.","subprocess.","ctypes.","sys._getframe","sys.settrace","sys.setprofile")) or event in (
            "import","compile","exec","marshal.loads","sys.addaudithook","gc.get_objects","gc.get_referrers"
        ):
            raise PermissionError("Closed public improvement worker")
    sys.addaudithook(deny)
    pub = strategy = None
    for line in sys.stdin:
        value = json.loads(line)
        if strategy is None and set(value) == {"policy"}:
            config = value["policy"]
            if set(config) != {"track","theta","no_probe"}:
                raise ValueError("Unexpected descriptor fields")
            strategy = Policy(space,settings,config["track"],config["theta"],config["no_probe"])
            answer = {"configured":True}
        elif strategy is not None and pub is None and set(value)=={"public"}:
            pub = value["public"]
            answer = {"ready":True,"role":"T5"}
        elif pub is not None and set(value)=={"view"}:
            answer = strategy.dispatch(pub,value["view"])
        elif set(value)=={"close"}:
            break
        else:
            raise ValueError("Unexpected public message")
        print(json.dumps(answer,sort_keys=True,separators=(",",":"),allow_nan=False),flush=True)


if __name__ == "__main__":
    main()

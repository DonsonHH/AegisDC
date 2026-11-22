"""Restrict a fresh process to the registered public frames and a fixed descriptor."""
import json
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    from aegis_dc.joint_resources import transit
    from aegis_risk_dispatch import knowledge, policy
    from aegis_improvement.policy import Selector

    space = json.loads((root/"parameter-space.json").read_bytes())
    settings = json.loads((root/"aegis_risk_dispatch/settings.json").read_bytes())
    settings["maintenance_capacity"] = 0.5
    for architecture in ("ordinary","power_board","cooling_board"):
        knowledge.catalogue(architecture)

    def deny(event,args):
        if event.startswith(("open","os.","socket.","subprocess.","ctypes.","sys._getframe","sys.settrace","sys.setprofile")) or event in (
            "import","compile","exec","marshal.loads","sys.addaudithook","gc.get_objects","gc.get_referrers"
        ):
            raise PermissionError("Closed public improvement worker")
    sys.addaudithook(deny)
    pub = selector = None
    for line in sys.stdin:
        msg = json.loads(line)
        if selector is None and set(msg)=={"policy"}:
            spec = msg["policy"]
            if set(spec)!={"track","theta","no_probe"}:
                raise ValueError("Unexpected descriptor field")
            selector = Selector(space,spec["track"],spec["theta"],settings,spec["no_probe"])
            answer = {"configured":True}
        elif pub is None and selector is not None and set(msg)=={"public"}:
            pub=msg["public"]
            answer={"ready":True,"role":"T5"}
        elif pub is not None and set(msg)=={"view"}:
            answer=selector.decide(pub,msg["view"])
        elif set(msg)=={"close"}:
            break
        else:
            raise ValueError("Unexpected public envelope")
        print(json.dumps(answer,sort_keys=True,separators=(",",":"),allow_nan=False),flush=True)


if __name__=="__main__":
    main()

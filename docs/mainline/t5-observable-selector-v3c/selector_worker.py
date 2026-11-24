"""Public-only selection process. Its only files are this module and selector.py."""
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from selector import catalogue,features,signals,select

def main():
    public=None;history=[];previous=-60;selected=None
    for line in sys.stdin:
        msg=json.loads(line)
        if msg=={"close":True}:break
        if public is None and set(msg)=={"subjects","lock"}:
            assert set(msg["lock"])=={"winner","cells"}
            public=catalogue({"subjects":msg["subjects"]});lock=msg["lock"];reply={"ready":True}
        else:
            assert public is not None and set(msg)=={"view","any_nonempty"} and selected is None
            view=msg["view"];assert set(view)=={"time","records","fixed","writes","work","paid","issued"}
            assert view["time"]==previous+60 and type(msg["any_nonempty"]) is bool
            previous=view["time"];history.append(signals(view))
            cell=features(public,history) if msg["any_nonempty"] else None
            if cell is not None:selected=select(lock,cell)
            reply={"cell":cell,"selected":selected}
        print(json.dumps(reply,sort_keys=True,separators=(",",":"),allow_nan=False),flush=True)

if __name__=="__main__":main()

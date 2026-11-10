"""One human result label; preserve program enums and historical sealed artifacts."""
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
SCOPE_PATH=ROOT/'docs/mainline/preset-study-scope.json'


def qualify_prose(text):
    scope=json.loads(SCOPE_PATH.read_bytes());prefix=scope['qualifier'];tag=scope['result_enum']
    return re.sub(r'(?<!'+re.escape(prefix)+')'+re.escape(tag),lambda _m:prefix+tag,text)


def qualify_visible_html(text):
    protected=[]
    def keep(match):
        protected.append(match.group(0));return 'SCOPE_PROTECTED_CHUNK_'+str(len(protected)-1)+'_END'
    text=re.sub(r'<(script|style)\b[^>]*>.*?</\1>',keep,text,flags=re.S|re.I)
    parts=re.split(r'(<[^>]+>)',text)
    text=''.join(part if i%2 else qualify_prose(part) for i,part in enumerate(parts))
    for i,chunk in enumerate(protected):text=text.replace('SCOPE_PROTECTED_CHUNK_'+str(i)+'_END',chunk)
    return text

"""Print parts of Buffer's API schema (read-only). Used to check which posting options Buffer offers.
Prints field and option names only, never the key. Always exits 0, so a check never emails a failure."""
import json
import os
import sys
import urllib.request

API = os.environ.get("BUFFER_URL", "https://api.buffer.com")
TYPES = ["SchedulingType", "ShareMode", "CreatePostInput", "PostInputMetaData", "TikTokPostMetadataInput",
         "PostStatus", "Post"]
Q = """query($name: String!) { __type(name: $name) { name kind
  enumValues { name description } inputFields { name description type { name kind ofType { name kind } } }
  fields { name } } }"""


def main():
    key = os.environ.get("BUFFER_API_KEY")
    if not key:
        print("No BUFFER_API_KEY secret, nothing checked.")
        return
    for name in TYPES:
        body = json.dumps({"query": Q, "variables": {"name": name}}).encode()
        req = urllib.request.Request(API, data=body, method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "greenline-poster"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                out = json.load(r)
        except Exception as e:
            print(f"{name}: request failed ({type(e).__name__})")
            continue
        t = (out.get("data") or {}).get("__type")
        if not t:
            print(f"{name}: not found {[(e.get('message') or '')[:120] for e in out.get('errors') or []]}")
            continue
        print(f"== {name} ({t['kind']})")
        for v in t.get("enumValues") or []:
            print(f"  enum {v['name']}: {(v.get('description') or '')[:160]}")
        for f in t.get("inputFields") or []:
            ty = f["type"]
            tn = ty.get("name") or (ty.get("ofType") or {}).get("name")
            print(f"  input {f['name']}: {tn}  {(f.get('description') or '')[:160]}")
        if name == "Post":
            print("  fields " + ", ".join(f["name"] for f in t.get("fields") or []))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Check stopped: {type(e).__name__}")
    sys.exit(0)

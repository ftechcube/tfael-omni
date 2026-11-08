#!/usr/bin/env python3
"""Test all Intel Graph API endpoints on Mac server."""
import urllib.request, json, sys, os

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"

# Login — credentials dari env, BUKAN hardcoded
_user = os.environ.get("OMNI_TEST_USER", "komandan")
_pass = os.environ.get("OMNI_TEST_PASS", "")
if not _pass:
    print("ERROR: Set env OMNI_TEST_PASS sebelum jalankan test.")
    print("  export OMNI_TEST_PASS='password_anda'")
    sys.exit(1)

req = urllib.request.Request(f"{BASE}/api/v2/auth/login",
    data=json.dumps({"username": _user, "password": _pass}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
token = json.loads(urllib.request.urlopen(req).read())["token"]
print("LOGIN OK")

def api(path, body={}):
    r = urllib.request.Request(f"{BASE}/api/v2/intel-graph/{path}",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type":"application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r).read())

# 1. Centrality
d = api("centrality", {"top_n": 5})
ranked = d.get("ranked", [])
assert len(ranked) >= 5, f"Centrality: expected >=5, got {len(ranked)}"
assert "node_id" in ranked[0], "Centrality: missing node_id"
print(f"CENTRALITY OK: {len(ranked)} items, top={ranked[0]['node_id']}")

# 2. Communities
d = api("communities")
comms = d.get("communities", [])
assert len(comms) >= 1, f"Communities: expected >=1, got {len(comms)}"
assert isinstance(comms[0]["members"][0], str), f"Communities: members[0] is {type(comms[0]['members'][0]).__name__}, expected str"
print(f"COMMUNITIES OK: {len(comms)} groups, members type=str")

# 3. Shortest Path
d = api("shortest-path", {"node_a":"TGT-ALPHA","node_b":"TGT-ECHO"})
assert d.get("found"), "Shortest path: not found"
assert isinstance(d["path"][0], str), f"Shortest path: path[0] is {type(d['path'][0]).__name__}, expected str"
print(f"SHORTEST PATH OK: hops={d['hops']}, path type=str")

# 4. Threat Scores
d = api("threat-scores")
scored = d.get("scored", [])
assert len(scored) >= 1, f"Threat scores: expected >=1, got {len(scored)}"
assert "node_id" in scored[0], "Threat scores: missing node_id"
assert "tier" in scored[0], "Threat scores: missing tier"
print(f"THREAT SCORES OK: {len(scored)} scored, top={scored[0]['node_id']} tier={scored[0]['tier']}")

# 5. Attack Paths
d = api("attack-paths", {"target_id":"TGT-ALPHA"})
paths = d.get("paths", [])
assert "assessment" in d, "Attack paths: missing assessment"
assert "risk_level" in d["assessment"], "Attack paths: missing risk_level"
assert "pivot_points" in d, "Attack paths: missing pivot_points"
print(f"ATTACK PATHS OK: {len(paths)} paths, risk={d['assessment']['risk_level']}, pivots={len(d['pivot_points'])}")

# 6. Stats
d = api("stats")
assert "total_nodes" in d, "Stats: missing total_nodes"
print(f"STATS OK: {d['total_nodes']} nodes, {d.get('total_edges',0)} edges")

# 7. Graph (unified)
d = api("graph")
assert "nodes" in d, "Graph: missing nodes"
assert "edges" in d, "Graph: missing edges"
print(f"GRAPH OK: {len(d['nodes'])} nodes, {len(d['edges'])} edges")

print("\nALL 7 API TESTS PASSED")

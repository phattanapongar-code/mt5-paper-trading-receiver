"""Auto-assign positions to all _graph.json nodes based on topological layering."""
import json
from pathlib import Path
from collections import deque

STRATEGIES_DIR = Path(__file__).resolve().parent.parent / "app" / "multibot" / "visual_strategies"
X_GAP = 260
Y_GAP = 80
Y_START = 40

def assign_positions(nodes, edges):
    adj = {n["id"]: [] for n in nodes}
    in_deg = {n["id"]: 0 for n in nodes}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in adj and t in adj:
            adj[s].append(t)
            in_deg[t] = in_deg.get(t, 0) + 1

    q = deque([nid for nid, d in in_deg.items() if d == 0])
    layer = {}
    for nid in q:
        layer[nid] = 0
    while q:
        u = q.popleft()
        for v in adj[u]:
            in_deg[v] -= 1
            layer[v] = max(layer.get(v, 0), layer[u] + 1)
            if in_deg[v] == 0:
                q.append(v)

    for n in nodes:
        if n["id"] not in layer:
            layer[n["id"]] = 0

    by_layer: dict[int, list[str]] = {}
    for nid, l in layer.items():
        by_layer.setdefault(l, []).append(nid)
    for l in sorted(by_layer):
        by_layer[l].sort()

    pos_map = {}
    y_counts: dict[int, int] = {}
    for nid in sorted(layer, key=lambda x: (layer[x], by_layer[layer[x]].index(x))):
        l = layer[nid]
        y = Y_START + y_counts.get(l, 0) * Y_GAP
        pos_map[nid] = {"x": l * X_GAP, "y": y}
        y_counts[l] = y_counts.get(l, 0) + 1

    return pos_map


def main():
    for fp in sorted(STRATEGIES_DIR.glob("*_graph.json")):
        data = json.loads(fp.read_text("utf-8"))
        pos = assign_positions(data["nodes"], data["edges"])
        for n in data["nodes"]:
            n["position"] = pos[n["id"]]
        fp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")
        print(f"  [OK] {fp.name}  ({len(data['nodes'])} nodes)")


if __name__ == "__main__":
    main()

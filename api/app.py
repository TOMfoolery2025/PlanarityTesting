# app.py (SVG-based, no Matplotlib / no Pillow)

import networkx as nx
from flask import Flask, request, jsonify
from flask_cors import CORS
import io
import base64
import html

app = Flask(__name__)
CORS(app)


## ------------------------
## Helper: Kuratowski logic
## ------------------------

def is_complete_graph_custom(G):
    if not G.number_of_nodes():
        return True
    required_degree = G.number_of_nodes() - 1
    for node, degree in G.degree():
        if degree != required_degree:
            return False
    return True


def get_kuratowski_type(graph):
    num_nodes = graph.number_of_nodes()
    if num_nodes == 5 and is_complete_graph_custom(graph):
        return "K_5"
    if num_nodes == 6 and nx.is_bipartite(graph):
        try:
            p1, p2 = nx.bipartite.sets(graph)
            if len(p1) == 3 and len(p2) == 3:
                return "K_3,3"
        except Exception:
            pass
    if num_nodes >= 5 and is_complete_graph_custom(graph):
        return "K_5 Subdivision"
    if num_nodes >= 6 and nx.is_bipartite(graph):
        return "K_3,3 Subdivision"
    return "Kuratowski Minor"


def get_kuratowski_minor(subdivision_graph):
    G_minor = subdivision_graph.copy()
    while True:
        degree_two_nodes = [n for n, d in dict(G_minor.degree()).items() if d == 2]
        if not degree_two_nodes:
            break
        u = degree_two_nodes[0]
        neighbors = list(G_minor.neighbors(u))
        if len(neighbors) == 2:
            v1, v2 = neighbors[0], neighbors[1]
            if v1 != v2 and not G_minor.has_edge(v1, v2):
                G_minor.add_edge(v1, v2)
            G_minor.remove_node(u)
    G_minor.remove_nodes_from(list(nx.isolates(G_minor)))
    return G_minor


## ------------------------
## SVG rendering helpers
## ------------------------

def _normalize_positions(pos):
    # pos: dict node -> (x,y)
    xs = [x for x, y in pos.values()] if pos else [0]
    ys = [y for x, y in pos.values()] if pos else [0]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x if max_x != min_x else 1.0
    height = max_y - min_y if max_y != min_y else 1.0
    return min_x, min_y, width, height


def graph_to_svg(G, pos, highlight_edges=None, title=None, width_px=800, height_px=800, node_style=None):
    """
    Render G to an SVG string using provided positions.
    highlight_edges: set of edge tuples (u,v) to draw in highlight color
    node_style: dict to override node appearance
    """
    if highlight_edges is None:
        highlight_edges = set()
    else:
        # normalize tuple ordering for undirected edges
        highlight_edges = {tuple(sorted(e)) for e in highlight_edges}

    # default styles
    node_style = node_style or {}
    node_radius = node_style.get("r", 18)
    node_color = node_style.get("fill", "#76c7ff")  # skyblue
    node_stroke = node_style.get("stroke", "#1f6feb")
    edge_color = node_style.get("edge_color", "#444")
    label_color = node_style.get("label", "#ffffff")
    highlight_color = node_style.get("highlight_color", "#e63946")  # red-ish

    # compute viewport box from pos
    min_x, min_y, w, h = _normalize_positions(pos)
    padding = max(w, h) * 0.12
    vb_min_x = min_x - padding
    vb_min_y = min_y - padding
    vb_w = w + 2 * padding
    vb_h = h + 2 * padding

    # Start SVG
    parts = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb_min_x} {vb_min_y} {vb_w} {vb_h}" '
                 f'width="{width_px}" height="{height_px}" preserveAspectRatio="xMidYMid meet">')

    if title:
        safe_title = html.escape(title)
        parts.append(f'<title>{safe_title}</title>')

    # background (optional, transparent)
    # parts.append(f'<rect x="{vb_min_x}" y="{vb_min_y}" width="{vb_w}" height="{vb_h}" fill="white" />')

    # Draw edges: normal edges first (lighter), then highlight edges on top
    for u, v in G.edges():
        if u not in pos or v not in pos:
            continue
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        edge_key = tuple(sorted((u, v)))
        if edge_key in highlight_edges:
            # skip for now, draw highlighted edges later
            continue
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{edge_color}" stroke-width="2" stroke-linecap="round" opacity="0.75" />')

    # highlighted edges (draw on top)
    for e in highlight_edges:
        u, v = e
        if u not in pos or v not in pos:
            continue
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{highlight_color}" stroke-width="4" stroke-linecap="round" opacity="0.95" />')

    # Draw nodes
    for n in G.nodes():
        if n not in pos:
            continue
        x, y = pos[n]
        parts.append(
            f'<circle cx="{x}" cy="{y}" r="{node_radius}" fill="{node_color}" stroke="{node_stroke}" stroke-width="2" />')
        # label centered
        safe_label = html.escape(str(n))
        # text anchor middle, dominant-baseline central
        parts.append(
            f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="central" font-family="Arial, Helvetica, sans-serif" font-size="{max(10, node_radius)}" fill="{label_color}">{safe_label}</text>')

    parts.append('</svg>')
    svg = "\n".join(parts)
    return svg


## ------------------------
## Main visualize function
## ------------------------

def visualize_planarity_test(graph_data):
    """
    Input graph_data expected to be:
    {
      "nodes": [{"id": "A", "x": 10, "y": 20}, ...],
      "edges": [{"source": "A", "target": "B"}, ...]
    }

    Returns: svg_original (bytes), svg_subdivision (bytes or None), svg_minor (bytes or None),
             title (str), kuratowski_type (str or None), kuratowski_edges (list)
    """
    try:
        edges = [(e['source'], e['target']) for e in graph_data['edges']]
        pos = {n['id']: (float(n['x']), float(n['y'])) for n in graph_data['nodes']}
    except Exception as e:
        return None, None, None, None, f"Data parsing error: {e}", None

    G = nx.Graph()
    G.add_edges_from(edges)

    # run planarity
    is_planar, counterexample_graph = nx.check_planarity(G, counterexample=True)

    title = "Graph is Planar" if is_planar else "Graph is NON-Planar (Kuratowski Counterexample Found)"
    kuratowski_edges = []
    svg_original = graph_to_svg(G, pos, highlight_edges=set(), title=title)

    svg_subdivision = None
    svg_minor = None
    kuratowski_type = None

    if not is_planar and counterexample_graph is not None:
        # highlight subdivision edges on the original layout (match node names)
        try:
            kuratowski_edges = [tuple(sorted(e)) for e in counterexample_graph.edges()]
        except Exception:
            kuratowski_edges = []

        svg_subdivision = graph_to_svg(G, pos, highlight_edges=set(kuratowski_edges),
                                       title=f"Intermediate Subdivision ({len(counterexample_graph.nodes())} vertices)")

        # create minor and draw it (we'll lay it out with a circular layout for clarity)
        kuratowski_minor = get_kuratowski_minor(counterexample_graph)
        kuratowski_type = get_kuratowski_type(kuratowski_minor)

        # For the minor, compute a simple layout (circular) and scale to reasonable coords
        minor_pos = {}
        if kuratowski_minor.number_of_nodes() > 0:
            circ = nx.circular_layout(kuratowski_minor)
            # multiply positions to look similar scale-wise
            for node, (x, y) in circ.items():
                minor_pos[node] = (float(x) * 200.0, float(y) * 200.0)
        svg_minor = graph_to_svg(kuratowski_minor, minor_pos, highlight_edges=set(),
                                 title=f"Minimal Kuratowski Minor: {kuratowski_type}")

        kuratowski_type = kuratowski_type

    # convert SVG strings to bytes
    svg_original_b = svg_original.encode("utf-8")
    svg_sub_b = svg_subdivision.encode("utf-8") if svg_subdivision else None
    svg_minor_b = svg_minor.encode("utf-8") if svg_minor else None

    return svg_original_b, svg_sub_b, svg_minor_b, title, kuratowski_type, kuratowski_edges


## ------------------------
## Flask endpoint
## ------------------------

@app.route('/planarity', methods=['POST'])
def planarity_api():
    data = request.get_json()
    if not data or 'nodes' not in data or 'edges' not in data:
        return jsonify({"error": "Invalid input format. Expected JSON with 'nodes' and 'edges'."}), 400

    svg_original_b, svg_sub_b, svg_minor_b, result_title, kuratowski_type, kuratowski_edges = visualize_planarity_test(
        data)

    if svg_original_b is None:
        return jsonify({"error": result_title}), 400

    # Return base64-encoded SVG data URIs (client can use them as image src)
    image_original = base64.b64encode(svg_original_b).decode('utf-8')
    image_subdivision = base64.b64encode(svg_sub_b).decode('utf-8') if svg_sub_b else None
    image_minor = base64.b64encode(svg_minor_b).decode('utf-8') if svg_minor_b else None

    return jsonify({
        "status": "success",
        "title": result_title,
        "is_planar": (image_subdivision is None),
        "kuratowski_type": kuratowski_type,
        "kuratowski_edges": [list(e) for e in kuratowski_edges],
        "image_original": image_original,
        "image_subdivision": image_subdivision,
        "image_minor": image_minor
    }), 200


@app.route('/', methods=['GET'])
def root_status():
    return "Planarity Testing API (SVG) is Running!", 200


if __name__ == "__main__":
    app.run(debug=True)

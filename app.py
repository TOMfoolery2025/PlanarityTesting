# app.py (FINAL FIXED VERSION)
import matplotlib

matplotlib.use('Agg')

import networkx as nx
import matplotlib.pyplot as plt
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io

app = Flask(__name__)
CORS(app)


## ----------------------------------------------------------------------
## KURATOWSKI IDENTIFICATION AND VISUALIZATION FUNCTIONS (MUST COME FIRST)
## ----------------------------------------------------------------------

# app.py (New helper function)

def is_complete_graph_custom(G):
    """
    Checks if a NetworkX graph G is a complete graph (K_n).
    A graph is complete if every node is connected to every other node.
    This means the degree of every node must be N - 1.
    """
    if not G.number_of_nodes():
        return True  # An empty graph is trivially complete

    # N is the required degree for every node (Total nodes - 1)
    required_degree = G.number_of_nodes() - 1

    # Check if every node has the required degree
    for node, degree in G.degree():
        if degree != required_degree:
            return False

    # If the loop finishes, all nodes have the maximum required edges
    return True


def get_kuratowski_type(graph):
    """
    Identifies if the graph is a subdivision of K5 or K3,3 based on node count and structure.
    NOTE: nx.check_planarity usually returns a subdivision, which may have > 5 or 6 nodes.
    This check is most reliable on the MINOR graph.
    """
    num_nodes = graph.number_of_nodes()

    # K5 Minor Check: 5 nodes, is a complete graph (or close enough)
    if num_nodes == 5 and is_complete_graph_custom(graph):
        return "K_5"

    # K3,3 Minor Check: 6 nodes, is bipartite and complete bipartite
    if num_nodes == 6 and nx.is_bipartite(graph):
        # Additional check to confirm it is K3,3 (3x3 complete bipartite)
        try:
            p1, p2 = nx.bipartite.sets(graph)
            if len(p1) == 3 and len(p2) == 3:
                return "K_3,3"
        except:
            # Fallback if bipartite sets fail
            pass

    # If the minor is a subdivision, classify based on minimum size
    if num_nodes >= 5 and is_complete_graph_custom(graph):
        return "K_5 Subdivision"
    if num_nodes >= 6 and nx.is_bipartite(graph):
        return "K_3,3 Subdivision"

    return "Kuratowski Minor"


def get_kuratowski_minor(subdivision_graph):
    """
    Simplifies the Kuratowski subdivision by repeatedly contracting edges
    incident to vertices of degree 2, revealing the minor (K5 or K3,3).
    """
    G_minor = subdivision_graph.copy()

    # --- FIX 3: Robust Contraction Loop ---
    # We loop until no more degree-2 nodes are found
    while True:
        # Check all nodes for degree 2
        degree_two_nodes = [node for node, degree in dict(G_minor.degree()).items() if degree == 2]

        if not degree_two_nodes:
            break

        u = degree_two_nodes[0]
        neighbors = list(G_minor.neighbors(u))

        if len(neighbors) == 2:
            v1, v2 = neighbors[0], neighbors[1]

            # Simulate edge contraction:
            # 1. Add edge between the two neighbors (if it doesn't exist)
            if v1 != v2 and not G_minor.has_edge(v1, v2):
                G_minor.add_edge(v1, v2)

            # 2. Remove the intermediate degree-2 node
            G_minor.remove_node(u)

    G_minor.remove_nodes_from(list(nx.isolates(G_minor)))

    return G_minor


def visualize_kuratowski_subdivision(counterexample_graph):
    plt.figure(figsize=(6, 6))

    # Use the function to get the most specific type for the title
    kuratowski_type = get_kuratowski_type(counterexample_graph)

    if kuratowski_type.startswith("K_5"):
        layout = nx.circular_layout(counterexample_graph)
        node_color = 'r'
    elif kuratowski_type.startswith("K_3,3"):
        try:
            partition_a, partition_b = nx.bipartite.sets(counterexample_graph)
            layout = nx.bipartite_layout(counterexample_graph, partition_a)
        except:
            layout = nx.circular_layout(counterexample_graph)
        node_color = 'darkorange'
    else:
        layout = nx.spring_layout(counterexample_graph)
        node_color = 'darkred'

    plt.title(f"Intermediate Subdivision: {kuratowski_type}", fontsize=12, color=node_color)
    nx.draw(counterexample_graph, layout,
            with_labels=True, node_color=node_color, node_size=800,
            font_color='white', font_weight='bold', edge_color='k', width=2)
    plt.axis('off')

    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight')
    plt.close()
    img_buffer.seek(0)

    return img_buffer, kuratowski_type


def visualize_kuratowski_minor(kuratowski_minor):
    plt.figure(figsize=(6, 6))

    kuratowski_type = get_kuratowski_type(kuratowski_minor)  # Use this type for the title

    if kuratowski_type == "K_5":
        layout = nx.circular_layout(kuratowski_minor)
        node_color = 'r'
        title = "Minimal Kuratowski Minor: K_5"
    elif kuratowski_type == "K_3,3":
        try:
            partition_a, partition_b = nx.bipartite.sets(kuratowski_minor)
            layout = nx.bipartite_layout(kuratowski_minor, partition_a)
        except:
            layout = nx.circular_layout(kuratowski_minor)
        node_color = 'darkorange'
        title = "Minimal Kuratowski Minor: K_3,3"
    else:
        layout = nx.spring_layout(kuratowski_minor)
        node_color = 'darkred'
        title = f"Minimal Minor: {kuratowski_type}"

    plt.title(title, fontsize=12, color=node_color)

    nx.draw(kuratowski_minor, layout,
            with_labels=True,
            node_color=node_color,
            node_size=800,
            font_color='white',
            font_weight='bold',
            edge_color='k',
            width=2)

    plt.axis('off')

    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight')
    plt.close()
    img_buffer.seek(0)

    return img_buffer, title


## ----------------------------------------------------------------------
## MAIN PLANARITY TEST FUNCTION
## ----------------------------------------------------------------------

def visualize_planarity_test(graph_data):
    """
    Performs a planarity test and returns the image file data (bytes)
    of the visualization, or None if input is invalid.
    """
    try:
        edges = [(e['source'], e['target']) for e in graph_data['edges']]
        pos = {n['id']: (n['x'], n['y']) for n in graph_data['nodes']}
    except (KeyError, TypeError) as e:
        # Return all required values on failure
        # FIX: Ensure all return values are provided
        return None, None, None, f"Data parsing error: Missing key or incorrect type. Details: {e}", None

    G = nx.Graph()
    G.add_edges_from(edges)

    is_planar, counterexample_graph = nx.check_planarity(G, counterexample=True)

    # --- (Visualization setup for the ORIGINAL graph remains the same) ---
    plt.figure(figsize=(8, 8))

    if is_planar:
        title, result_color, edge_color, kuratowski_edges = "Graph is Planar", 'green', 'blue', []
    else:
        title, result_color, edge_color = f"Graph is NON-Planar (Kuratowski Counterexample Found)", 'red', 'gray'
        kuratowski_edges = list(counterexample_graph.edges())

    plt.title(title, fontsize=14, color=result_color)
    nx.draw_networkx_edges(G, pos, edge_color=edge_color, alpha=0.5, width=1.5)

    if not is_planar:
        nx.draw_networkx_edges(G, pos, edgelist=kuratowski_edges, edge_color='r', width=3,
                               label='Kuratowski Subdivision')
        max_y = max((y for _, y in pos.values()), default=0)
        plt.text(0, max_y * 1.05,
                 f"Non-Planar due to Kuratowski subdivision: Vertices = {counterexample_graph.number_of_nodes()}",
                 fontsize=10, color='r')

    nx.draw_networkx_nodes(G, pos, node_color='skyblue', node_size=700)
    nx.draw_networkx_labels(G, pos, font_weight='bold')

    # Finalize and Return Image in Memory
    plt.axis('off')
    plt.gca().set_aspect('equal', adjustable='box')

    img_buffer_original = io.BytesIO()
    plt.savefig(img_buffer_original, format='png', bbox_inches='tight')
    plt.close()
    img_buffer_original.seek(0)

    img_buffer_kuratowski_subdivision = None
    img_buffer_kuratowski_minor = None
    kuratowski_type = None

    if not is_planar:
        # 1. Generate the second visualization (Kuratowski Subdivision)
        # NOTE: The second image is using the node coordinates found by NetworkX, which might not be clean.
        img_buffer_kuratowski_subdivision, kuratowski_subdivision_type = visualize_kuratowski_subdivision(
            counterexample_graph)
        kuratowski_type = f"Subdivision of {kuratowski_subdivision_type}"

        # 2. Get the Minimal Minor (remove degree-2 nodes)
        kuratowski_minor = get_kuratowski_minor(counterexample_graph)

        # 3. Generate the third visualization (Kuratowski Minor)
        img_buffer_kuratowski_minor, minor_title = visualize_kuratowski_minor(kuratowski_minor)
        # Update type based on the clean minor
        kuratowski_type = minor_title.replace("Minimal Kuratowski Minor: ", "")

    return img_buffer_original, img_buffer_kuratowski_subdivision, img_buffer_kuratowski_minor, title, kuratowski_type


## ----------------------------------------------------------------------
## FLASK API ENDPOINT
## ----------------------------------------------------------------------

@app.route('/planarity', methods=['POST'])
def planarity_api():
    """API endpoint to receive graph data and return the planarity images (Base64)."""

    data = request.get_json()

    if not data or 'nodes' not in data or 'edges' not in data:
        return jsonify({"error": "Invalid input format. Expected JSON with 'nodes' and 'edges'."}), 400

    # FIX: Corrected variable names to match the function return
    img_original, img_subdivision, img_minor, result_title, kuratowski_type = visualize_planarity_test(data)

    if img_original is None:
        return jsonify({"error": result_title}), 400

    import base64

    img_original_b64 = base64.b64encode(img_original.read()).decode('utf-8')

    img_subdivision_b64 = None
    img_minor_b64 = None

    if img_subdivision:
        img_subdivision_b64 = base64.b64encode(img_subdivision.read()).decode('utf-8')
        img_minor_b64 = base64.b64encode(img_minor.read()).decode('utf-8')

    # Return the three images and metadata as JSON
    return jsonify({
        "status": "success",
        "title": result_title,
        "is_planar": img_subdivision_b64 is None,
        "kuratowski_type": kuratowski_type,
        "image_original": img_original_b64,
        "image_subdivision": img_subdivision_b64,
        "image_minor": img_minor_b64
    }), 200


if __name__ == '__main__':

    app.run(debug=True)

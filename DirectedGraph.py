import Node
import Edge

class DirectedGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}

    def add_node(self, id, label):
        node = Node.Node(id, label)
        self.nodes[id] = node

    def find_node(self, id):
        return self.nodes.get(id, None)

    def add_edge(self, src, dst, polarity):
        src_node = self.find_node(src)
        dst_node = self.find_node(dst)

        edge = Edge.Edge(src, dst, polarity)
        self.edges[src, dst] = edge
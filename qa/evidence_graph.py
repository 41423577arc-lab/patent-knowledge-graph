"""Build an evidence graph from witnessed relationships, keeping endpoint direction."""
class EvidenceGraph:
    ENDPOINTS = {
        "APPLIES_FOR": ("Applicant", "Patent"), "CITES": ("Patent", "Patent"),
        "HAS_IPC": ("Patent", "IPC"), "INVOLVES": ("Patent", "Technology"),
        "BELONGS_TO": ("Technology", "Domain"), "CO_APPLIED_WITH": ("Applicant", "Applicant"),
    }

    def __init__(self):
        self.nodes = {}
        self.edges = {}

    def edge(self, kind, source, target, weight=1):
        if not source or not target:
            return
        endpoints = []
        for node_type, label in zip(self.ENDPOINTS[kind], (source, target)):
            key = f"{node_type}:{label}"
            self.nodes[key] = {"id": key, "label": str(label), "type": node_type}
            endpoints.append(key)
        left, right = endpoints
        self.edges[left, right, kind] = {"source": left, "target": right, "type": kind, "weight": weight}

    def technology(self, patent, topic, domain):
        self.edge("INVOLVES", patent, topic)
        self.edge("BELONGS_TO", topic, domain)

    def citation(self, applicant, patent, cited, target):
        self.edge("APPLIES_FOR", applicant, patent)
        self.edge("CITES", patent, cited)
        self.edge("APPLIES_FOR", target, cited)

    @property
    def public(self):
        return {"nodes": list(self.nodes.values()), "edges": list(self.edges.values())}

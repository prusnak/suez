import requests


class TerminalWeb:
    def __init__(self, local_pubkey, show_scores, show_good_peers):
        self.local_pubkey = local_pubkey
        self.show_scores = show_scores
        self.show_good_peers = show_good_peers
        if show_scores or show_good_peers:
            try:
                r = requests.get(
                    "https://ln-scores.prod.lightningcluster.com/availability/v3/btc_summary.json",
                    headers={"referer": "https://terminal.lightning.engineering/"},
                )
                j = r.json()
                self.nodes = j["scored"]
                self.local_node = self.nodes.get(local_pubkey)
            except:
                self.nodes = {}
                self.local_node = None

    def is_good_inbound_peer(self, remote_pubkey):
        if not self.local_node or "good_inbound_peers" not in self.local_node:
            return False
        return remote_pubkey in self.local_node["good_inbound_peers"]

    def is_good_outbound_peer(self, remote_pubkey):
        if not self.local_node or "good_outbound_peers" not in self.local_node:
            return False
        return remote_pubkey in self.local_node["good_outbound_peers"]

    def get_score(self, pubkey):
        node = self.nodes.get(pubkey)
        return node["score"] if node else None

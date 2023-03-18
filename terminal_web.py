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
        if not self.local_node or not "good_inbound_peers" in self.local_node:
            return False
        for pubkey in self.local_node["good_inbound_peers"]:
            if pubkey == remote_pubkey:
                return True
        return False

    def is_good_outbound_peer(self, remote_pubkey):
        if not self.local_node or not "good_outbound_peers" in self.local_node:
            return False
        for pubkey in self.local_node["good_outbound_peers"]:
            if pubkey == remote_pubkey:
                return True
        return False

    def get_score(self, pubkey):
        node = self.nodes.get(pubkey)
        return node["score"] if node else None

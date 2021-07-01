import requests


class BosScore:
    def __init__(self):
        try:
            r = requests.get(
                "https://nodes.lightning.computer/availability/v1/btc.json"
            )
            j = r.json()
            nodes = j["scores"]
        except:
            nodes = []
        self.scores = {}
        for n in nodes:
            self.scores[n["public_key"]] = n["score"]

    def get(self, key):
        return self.scores.get(key)

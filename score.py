import requests


class Score:
    JSON = (
        "https://ln-scores.prod.lightningcluster.com/availability/v1/btc_summary.json"
    )

    def __init__(self):
        try:
            r = requests.get(self.JSON)
            j = r.json()
            self.scores = j["scored"]
        except:
            self.scores = {}

    def get(self, key):
        s = self.scores.get(key)
        return s["score"] if s else None

import requests


class Score:
    def __init__(self):
        try:
            r = requests.get(
                "https://ln-scores.prod.lightningcluster.com/availability/v1/btc_summary.json",
                headers={"referer": "https://terminal.lightning.engineering/"},
            )
            j = r.json()
            self.scores = j["scored"]
        except:
            self.scores = {}

    def get(self, key):
        s = self.scores.get(key)
        return s["score"] if s else None

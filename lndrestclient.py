import codecs
import json
import posixpath
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from lndclient import LndClient


class LndRestClient(LndClient):
    def __init__(self, client_args):
        args = dict(a.split("=", 1) for a in client_args)

        self.rpcserver = (
            args["rpcserver"] if "rpcserver" in args else "https://localhost:8080"
        )
        self.macaroonpath = (
            Path(args["macaroonpath"])
            if "macaroonpath" in args
            else Path.home()
            / ".lnd"
            / "data"
            / "chain"
            / "bitcoin"
            / "mainnet"
            / "admin.macaroon"
        )
        self.tlscertpath = str(
            Path(args["tlscertpath"])
            if "tlscertpath" in args
            else Path.home() / ".lnd" / "tls.cert"
        )

        self.api_base = posixpath.join(self.rpcserver, "v1")

        with self.macaroonpath.open("rb") as f:
            macaroon = f.read().hex()
            self.headers = {"Grpc-Metadata-macaroon": macaroon}

        super().__init__(client_args)

    def getinfo(self):
        return self._do_get("getinfo")

    def listchannels(self):
        return self._do_get("channels")

    def getchaninfo(self, chan_id):
        return self._do_get("graph/edge", chan_id)

    def getnodeinfo(self, node_id):
        return self._do_get("graph/node", node_id)

    def fwd_events(self):
        start_date = datetime.now() - timedelta(days=30)
        return self._do_post(
            "switch",
            num_max_events=50000,
            start_time=str(int(time.mktime(start_date.timetuple()))),
        )

    def updatechanpolicy(self, channel, policy):
        base_fee, fee_rate, time_lock_delta = policy.calculate(channel)
        funding_txid_str, output_index = channel.channel_point.split(":")
        return self._do_post(
            "chanpolicy",
            chan_point={
                "funding_txid_str": funding_txid_str,
                "output_index": int(output_index),
            },
            base_fee_msat=str(base_fee),
            fee_rate=fee_rate,
            time_lock_delta=time_lock_delta,
        )

    def _do_get(self, method, *args):
        response = requests.get(
            posixpath.join(self.api_base, method, *args),
            headers=self.headers,
            verify=self.tlscertpath,
        )
        return json.loads(response.text)

    def _do_post(self, method, **data):
        response = requests.post(
            posixpath.join(self.api_base, method),
            headers=self.headers,
            data=json.dumps(data),
            verify=self.tlscertpath,
        )
        return json.loads(response.text)

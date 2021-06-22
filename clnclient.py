import json
import subprocess

from channel import Channel


class ClnClient:
    def __init__(self, client_args):
        self.client_args = client_args
        self.refresh()

    def refresh(self):
        gi = self._run("getinfo")
        self.local_pubkey = gi["id"]
        self.local_alias = gi["alias"]
        self.channels = {}

        timestamps, fees = {}, {}

        peers = self._run("listpeers")["peers"]
        for p in peers:
            if p["channels"]:
                c = p["channels"][0]
                chan = Channel()
                chan.chan_id = c["short_channel_id"]
                chan.active = c["state"] == "CHANNELD_NORMAL"
                chan.opener = c["opener"]
                chan.local_node_id, chan.remote_node_id = self.local_pubkey, p["id"]
                chan.channel_point = c["channel_id"]
                chan.uptime, chan.lifetime = None, None
                chan.capacity, chan.commit_fee = (
                    c["msatoshi_total"] // 1000,
                    int(c["last_tx_fee"].replace("msat", "")) // 1000,
                )
                chan.local_balance, chan.remote_balance = (
                    c["msatoshi_to_us"] // 1000,
                    (c["msatoshi_total"] - c["msatoshi_to_us"]) // 1000,
                )
                info = self._run("listchannels", chan.chan_id)["channels"]
                if len(info) > 0:
                    node1_fee = (
                        int(info[0]["base_fee_millisatoshi"]),
                        int(info[0]["fee_per_millionth"]),
                    )
                    if len(info) > 1:
                        node2_fee = (
                            int(info[1]["base_fee_millisatoshi"]),
                            int(info[1]["fee_per_millionth"]),
                        )
                        if info[0]["source"] != self.local_pubkey:
                            assert info[1]["source"] == self.local_pubkey
                            fee_remote = node1_fee
                            fee_local = node2_fee
                    if len(info) > 1:
                        if info[1]["source"] != self.local_pubkey:
                            assert info[0]["source"] == self.local_pubkey
                            fee_local = node1_fee
                            fee_remote = node2_fee
                    else:
                        fee_local = node1_fee
                        fee_remote = 0, 0

                chan.local_base_fee, chan.local_fee_rate = fee_local
                chan.remote_base_fee, chan.remote_fee_rate = fee_remote
                chan.local_alias = self.local_alias
                chan.remote_alias = self._run("listnodes", chan.remote_node_id)[
                    "nodes"
                ][0].get("alias")
                if not chan.remote_alias:
                    chan.remote_alias = chan.remote_node_id
                chan.last_forward = 0
                chan.local_fees = 0
                chan.remote_fees = 0

                self.channels[chan.chan_id] = chan

        fwd_events = self._run("listforwards", "status=settled")["forwards"]
        for fe in fwd_events:
            cin = fe["in_channel"]
            cout = fe["out_channel"]
            ts = int(fe["resolved_time"]) if "resolved_time" in fe else 0
            fee = fe["fee"] // 1000
            amount_in = fe["in_msatoshi"] // 1000
            if cin in self.channels:
                self.channels[cin].last_forward = max(
                    ts, self.channels[cin].last_forward
                )
                self.channels[cin].remote_fees += (
                    self.channels[cin].remote_base_fee
                    + (self.channels[cin].remote_fee_rate * amount_in // 1000)
                ) // 1000
            if cout in self.channels:
                self.channels[cout].last_forward = max(
                    ts, self.channels[cout].last_forward
                )
                self.channels[cout].local_fees += fee

    def apply_fee_policy(self, policy):
        for c in self.channels.values():
            base_fee, fee_rate, _ = policy.calculate(c)
            self._run(
                "setchannelfee", c.chan_id, str(base_fee), str(int(fee_rate * 1000000))
            )

    def _run(self, *args):
        if self.client_args:
            args = ["lightning-cli", self.client_args] + list(args)
        else:
            args = ["lightning-cli"] + list(args)
        j = subprocess.run(args, stdout=subprocess.PIPE)
        return json.loads(j.stdout)

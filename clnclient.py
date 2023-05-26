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

        peers = self._run("listpeers")["peers"]
        for p in peers:
            if p["channels"]:
                for c in p["channels"]:
                    chan = Channel()
                    chan.chan_id = c.get("short_channel_id")
                    chan.active = c["state"] == "CHANNELD_NORMAL"
                    chan.opener = c["opener"]
                    chan.private = c["private"]
                    chan.local_node_id, chan.remote_node_id = self.local_pubkey, p["id"]
                    chan.channel_point = c["channel_id"]
                    chan.uptime, chan.lifetime = None, None
                    total_msat = self._resolve_total_msat(c)
                    to_us_msat = self._resolve_to_us_msat(c)
                    chan.capacity, chan.commit_fee = (
                        total_msat // 1000,
                        self._cleanup_msat_value(c["last_tx_fee_msat"]) // 1000,
                    )
                    chan.local_balance, chan.remote_balance = (
                        to_us_msat // 1000,
                        (total_msat - to_us_msat) // 1000,
                    )
                    chan.ins = c["in_payments_fulfilled"]
                    chan.ins_percent = chan.outs_percent = 0
                    if chan.ins > 0:
                        chan.ins_percent = chan.ins / c["in_payments_offered"]
                    chan.outs = c["out_payments_fulfilled"]
                    if chan.outs > 0:
                        chan.outs_percent = chan.outs / c["out_payments_offered"]
                    if chan.chan_id is not None:
                        info = self._run("listchannels", chan.chan_id)["channels"]
                    else:
                        info = {}
                    if len(info) > 0:
                        node1_fee = (
                            int(info[0]["base_fee_millisatoshi"]),
                            int(info[0]["fee_per_millionth"]),
                        )
                        node1_htlc = (
                            self._cleanup_msat_value(info[0]["htlc_minimum_msat"]),
                            self._cleanup_msat_value(info[0]["htlc_maximum_msat"]),
                        )
                        node1_disabled = not info[0]["active"]
                        if len(info) > 1:
                            node2_fee = (
                                int(info[1]["base_fee_millisatoshi"]),
                                int(info[1]["fee_per_millionth"]),
                            )
                            node2_htlc = (
                                self._cleanup_msat_value(info[1]["htlc_minimum_msat"]),
                                self._cleanup_msat_value(info[1]["htlc_maximum_msat"]),
                            )
                            node2_disabled = not info[1]["active"]
                            if info[0]["source"] != self.local_pubkey:
                                assert info[1]["source"] == self.local_pubkey
                                fee_remote = node1_fee
                                fee_local = node2_fee
                                htlc_remote = node1_htlc
                                htlc_local = node2_htlc
                                disabled_remote = node1_disabled
                                disabled_local = node2_disabled
                        if len(info) > 1:
                            if info[1]["source"] != self.local_pubkey:
                                assert info[0]["source"] == self.local_pubkey
                                fee_local = node1_fee
                                fee_remote = node2_fee
                                htlc_local = node1_htlc
                                htlc_remote = node2_htlc
                                disabled_local = node1_disabled
                                disabled_remote = node2_disabled
                        else:
                            fee_local = node1_fee
                            fee_remote = 0, 0
                            htlc_local = node1_htlc
                            htlc_remote = None, None
                            disabled_local = node1_disabled
                            disabled_remote = None
                    else:
                        fee_local = 0, 0
                        fee_remote = 0, 0
                        htlc_local = None, None
                        htlc_remote = None, None
                        disabled_local = None
                        disabled_remote = None

                    chan.local_base_fee, chan.local_fee_rate = fee_local
                    chan.remote_base_fee, chan.remote_fee_rate = fee_remote
                    chan.local_min_htlc, chan.local_max_htlc = htlc_local
                    chan.remote_min_htlc, chan.remote_max_htlc = htlc_remote
                    chan.local_disabled = disabled_local
                    chan.remote_disabled = disabled_remote
                    chan.local_alias = self.local_alias
                    listnode = self._run("listnodes", chan.remote_node_id)
                    if len(listnode["nodes"]) > 0:
                        chan.remote_alias = listnode["nodes"][0].get(
                            "alias", chan.remote_node_id
                        )
                    else:
                        chan.remote_alias = chan.remote_node_id
                    chan.last_forward = 0
                    chan.local_fees_msat = 0
                    chan.remote_fees = 0

                    self.channels[chan.chan_id] = chan

        fwd_events = self._run("listforwards", "status=settled")["forwards"]
        for fe in fwd_events:
            cin = fe["in_channel"]
            cout = fe["out_channel"]
            ts = int(fe.get("resolved_time", 0))
            #
            # 23.05 naming change renamed everything to _msat
            if "fee" in fe:
                fee = fe["fee"]
                amount_in = fe["in_msatoshi"] // 1000
            else:
                fee = fe["fee_msat"]
                amount_in = fe["in_msat"] // 1000
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
                self.channels[cout].local_fees_msat += fee

    def apply_fee_policy(self, policy):
        for c in self.channels.values():
            if c.chan_id is not None:
                base_fee, fee_rate, _ = policy.calculate(c)
                self._run(
                    "setchannel",
                    c.chan_id,
                    str(base_fee),
                    str(int(fee_rate * 1000000)),
                )

    @staticmethod
    def _resolve_total_msat(channel):
        if "msatoshi_total" in channel:
            return int(channel["msatoshi_total"])
        return channel["total_msat"]

    @staticmethod
    def _resolve_to_us_msat(channel):
        if "msatoshi_to_us" in channel:
            return int(channel["msatoshi_to_us"])
        return channel["to_us_msat"]

    @staticmethod
    def _cleanup_msat_value(value):
        if isinstance(value, str):
            return int(value.replace("msat", ""))
        return value

    def _run(self, *args):
        if self.client_args:
            args = ["lightning-cli"] + list(self.client_args) + list(args)
        else:
            args = ["lightning-cli"] + list(args)
        j = subprocess.run(args, stdout=subprocess.PIPE)
        return json.loads(j.stdout)

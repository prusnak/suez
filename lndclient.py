import json
import subprocess

from channel import Channel


class LndClient:
    def __init__(self):
        self.refresh()

    def refresh(self):
        gi = self._run("getinfo")
        self.local_pubkey = gi["identity_pubkey"]
        self.local_alias = gi["alias"]
        self.channels = {}

        timestamps, fees = {}, {}

        fwd_events = self._run(
            "fwdinghistory", "--max_events", "50000", "--start_time", "-30d"
        )["forwarding_events"]
        for fe in fwd_events:
            c1 = fe["chan_id_in"]
            c2 = fe["chan_id_out"]
            ts = int(fe["timestamp"])
            fee = int(fe["fee"])
            timestamps[c1] = max(ts, timestamps.get(c1, 0))
            timestamps[c2] = max(ts, timestamps.get(c2, 0))
            if not c1 in fees:
                fees[c1] = 0
            if not c2 in fees:
                fees[c2] = 0
            fees[c1] += fee
            fees[c2] += fee

        channels = self._run("listchannels")["channels"]
        for c in channels:
            chan = Channel()
            chan.chan_id = c["chan_id"]
            chan.active = c["active"]
            chan.local_node_id, chan.remote_node_id = (
                self.local_pubkey,
                c["remote_pubkey"],
            )
            chan.channel_point = c["channel_point"]
            chan.uptime, chan.lifetime = int(c["uptime"]), int(c["lifetime"])
            chan.capacity, chan.local_balance, chan.remote_balance = (
                int(c["capacity"]),
                int(c["local_balance"]),
                int(c["remote_balance"]),
            )
            info = self._run("getchaninfo", chan.chan_id)
            node1_fee = (
                int(info["node1_policy"]["fee_base_msat"]),
                int(info["node1_policy"]["fee_rate_milli_msat"]),
            )
            node2_fee = (
                int(info["node2_policy"]["fee_base_msat"]),
                int(info["node2_policy"]["fee_rate_milli_msat"]),
            )
            if info["node1_pub"] != self.local_pubkey:
                assert info["node2_pub"] == self.local_pubkey
                fee_remote = node1_fee
                fee_local = node2_fee
            if info["node2_pub"] != self.local_pubkey:
                assert info["node1_pub"] == self.local_pubkey
                fee_local = node1_fee
                fee_remote = node2_fee
            chan.local_base_fee, chan.local_fee_rate = fee_local
            chan.remote_base_fee, chan.remote_fee_rate = fee_remote
            chan.local_alias = self.local_alias
            chan.remote_alias = self._run("getnodeinfo", chan.remote_node_id)["node"][
                "alias"
            ]
            chan.last_forward = timestamps.get(chan.chan_id, 0)
            chan.earned_fees = fees.get(chan.chan_id, 0)

            self.channels[chan.chan_id] = chan

    def apply_fee_policy(self, policy):
        for c in self.channels.values():
            base_fee, fee_rate, time_lock_delta = policy.calculate(c)
            self._run(
                "updatechanpolicy",
                "--base_fee_msat",
                str(base_fee),
                "--fee_rate",
                "%0.8f" % fee_rate,
                "--time_lock_delta",
                str(time_lock_delta),
                "--chan_point",
                c.channel_point,
            )

    def _run(self, *args):
        j = subprocess.run(("lncli",) + args, capture_output=True)
        return json.loads(j.stdout)

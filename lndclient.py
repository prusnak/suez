import abc
import json

from channel import Channel


class LndClient(abc.ABC):
    def __init__(self, client_args):
        self.client_args = client_args
        self.refresh()

    @abc.abstractmethod
    def getinfo(self):
        pass

    @abc.abstractmethod
    def listchannels(self):
        pass

    @abc.abstractmethod
    def getchaninfo(self, chan_id):
        pass

    @abc.abstractmethod
    def getnodeinfo(self, node_id):
        pass

    @abc.abstractmethod
    def fwd_events(self):
        pass

    @abc.abstractmethod
    def updatechanpolicy(self, channel_point, policy):
        pass

    def refresh(self):
        gi = self.getinfo()
        self.local_pubkey = gi["identity_pubkey"]
        self.local_alias = gi["alias"]
        self.channels = {}

        channels = self.listchannels()["channels"]
        for c in channels:
            chan = Channel()
            chan.chan_id = c["chan_id"]
            chan.active = c["active"]
            chan.opener = "local" if c["initiator"] else "remote"
            chan.local_node_id, chan.remote_node_id = (
                self.local_pubkey,
                c["remote_pubkey"],
            )
            chan.channel_point = c["channel_point"]
            chan.uptime, chan.lifetime = int(c["uptime"]), int(c["lifetime"])
            chan.capacity, chan.commit_fee, chan.local_balance, chan.remote_balance = (
                int(c["capacity"]),
                int(c["commit_fee"]),
                int(c["local_balance"]),
                int(c["remote_balance"]),
            )
            try:
                info = self.getchaninfo(chan.chan_id)
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
            except:
                chan.local_base_fee, chan.local_fee_rate = None, None
                chan.remote_base_fee, chan.remote_fee_rate = None, None
            chan.local_alias = self.local_alias
            chan.remote_alias = self.getnodeinfo(chan.remote_node_id)["node"]["alias"]
            chan.last_forward = 0
            chan.local_fees = 0
            chan.remote_fees = 0

            self.channels[chan.chan_id] = chan

        fwd_events = self.fwd_events()["forwarding_events"]
        for fe in fwd_events:
            cin = fe["chan_id_in"]
            cout = fe["chan_id_out"]
            ts = int(fe["timestamp"])
            fee = int(fe["fee"])
            amt_in = int(fe["amt_in"])
            amt_out = int(fe["amt_out"])
            if cin in self.channels:
                self.channels[cin].last_forward = max(
                    ts, self.channels[cin].last_forward
                )
                self.channels[cin].remote_fees += (
                    self.channels[cin].remote_base_fee
                    + self.channels[cin].remote_fee_rate * amt_in // 1000000
                )
            if cout in self.channels:
                self.channels[cout].last_forward = max(
                    ts, self.channels[cout].last_forward
                )
                self.channels[cout].local_fees += fee

    def apply_fee_policy(self, policy):
        for c in self.channels.values():
            self.updatechanpolicy(c, policy)

import json
import subprocess

from lndclient import LndClient


class LndCliClient(LndClient):
    def getinfo(self):
        return self._run("getinfo")

    def listchannels(self):
        return self._run("listchannels")

    def getchaninfo(self, chan_id):
        return self._run("getchaninfo", chan_id)

    def getnodeinfo(self, node_id):
        return self._run("getnodeinfo", node_id)

    def fwd_events(self):
        return self._run(
            "fwdinghistory", "--max_events", "50000", "--start_time", "-30d"
        )

    def updatechanpolicy(self, channel, policy):
        base_fee, fee_rate, time_lock_delta = policy.calculate(channel)
        return self._run(
            "updatechanpolicy",
            "--base_fee_msat",
            str(base_fee),
            "--fee_rate",
            "%0.8f" % fee_rate,
            "--time_lock_delta",
            str(time_lock_delta),
            "--chan_point",
            channel.channel_point,
        )

    def _run(self, *args):
        if self.client_args:
            args = ["lncli"] + list(self.client_args) + list(args)
        else:
            args = ["lncli"] + list(args)
        j = subprocess.run(args, stdout=subprocess.PIPE)
        return json.loads(j.stdout)

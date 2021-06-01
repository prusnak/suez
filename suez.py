#!/usr/bin/env python3
import subprocess
import json
import math
import requests

import click
from rich import box
from rich.console import Console
from rich.table import Table

class Channel:
    """
        self.node_id
        self.channel_id
        self.capacity
        self.local_balance_sat
        self.remote_balance_sat
        self.base_fee_local
        self.fee_rate_local
        self.base_fee_remote
        self.fee_rate_remote
        self.time_lock_delta_local
        self.remote_alias
        self.uptime
        self.lifetime
    """

class LndClient:
    def _run(self, *args):
        j = subprocess.run(("lncli",) + args, capture_output=True)
        return json.loads(j.stdout)

    def listchannels(self):
        channels = []
        for lnd_channel in self._run("listchannels")["channels"]:
            channel_info = self._getchaninfo(lnd_channel["chan_id"])
            if channel_info["node1_pub"] == lnd_channel["remote_pubkey"]:
                assert channel_info["node2_pub"] != lnd_channel["remote_pubkey"]
                local_policy = channel_info["node2_policy"]
                remote_policy = channel_info["node1_policy"]
            else:
                assert channel_info["node2_pub"] == lnd_channel["remote_pubkey"]
                local_policy = channel_info["node1_policy"]
                remote_policy = channel_info["node2_policy"]

            channel = Channel()
            channel.node_id = lnd_channel["remote_pubkey"]
            channel.channel_id = lnd_channel["chan_id"]
            channel.capacity = lnd_channel["capacity"]
            channel.active = lnd_channel["active"]
            channel.uptime = int(lnd_channel["uptime"])
            channel.lifetime = int(lnd_channel["lifetime"])
            channel.local_balance_sat = int(lnd_channel["local_balance"])
            channel.remote_balance_sat = int(lnd_channel["remote_balance"])
            channel.base_fee_local = int(local_policy["fee_base_msat"])
            channel.fee_rate_local = int(local_policy["fee_rate_milli_msat"])
            channel.base_fee_remote = int(remote_policy["fee_base_msat"])
            channel.fee_rate_remote = int(remote_policy["fee_rate_milli_msat"])
            channel.time_lock_delta_local = int(local_policy["time_lock_delta"])
            channel.remote_alias = self._getnodeinfo(channel.node_id)["alias"]
            channel.point = lnd_channel["channel_point"]

            channels.append(channel)

        return channels

    def _getnodeinfo(self, node):
        return self._run("getnodeinfo", node)["node"]

    def _getchaninfo(self, node):
        return self._run("getchaninfo", node)

    def updatechanpolicy(self, channel, base_fee, fee_rate, time_lock_delta):
        return self._run(
            "updatechanpolicy",
            "--base_fee_msat",
            str(base_fee),
            "--fee_rate",
            "%0.8f" % fee_rate,
            "--time_lock_delta",
            str(time_lock_delta),
            "--chan_point",
            channel.point,
        )

class EclairClient:
    def __init__(self, port, password):
        self._port = port
        self._password = password

    def _request(self, command, data = {}):
        resp = requests.post("http://127.0.0.1:%d/%s" % (self._port, command), data=data, auth=("eclair-cli", self._password))
        return resp

    def listchannels(self):
        nodes = {}
        for node in self._request("nodes").json():
            nodes[node["nodeId"]] = node

        channels = []
        for eclair_channel in self._request("channels").json():
            commitments = eclair_channel["data"]["commitments"]
            try:
                channel_update = eclair_channel["data"]["channelUpdate"]
            except KeyError:
                continue

            channel = Channel()
            channel.node_id = eclair_channel["nodeId"]
            channel.channel_id = eclair_channel["channelId"]
            channel.local_balance_sat = commitments["localCommit"]["spec"]["toLocal"] / 1000
            channel.remote_balance_sat = commitments["localCommit"]["spec"]["toRemote"] / 1000
            channel.capacity = channel.local_balance_sat + channel.remote_balance_sat
            channel.active = eclair_channel["state"] == "NORMAL"
            # Eclair doesn't seem to measure uptime
            channel.uptime = 1
            channel.lifetime = 1
            channel.base_fee_local = channel_update["feeBaseMsat"]
            channel.fee_rate_local = channel_update["feeProportionalMillionths"]
            # Unsure how to find fees
            channel.base_fee_remote = 0
            channel.fee_rate_remote = 0
            channel.time_lock_delta_local = channel_update["cltvExpiryDelta"]
            try:
                channel.remote_alias = nodes[channel.node_id]["alias"]
            except KeyError:
                channel.remote_alias = channel.node_id

            channels.append(channel)

        return channels

    def updatechanpolicy(self, channel, base_fee, fee_rate, time_lock_delta):
        pass

@click.command()
@click.option("--eclair-conf", default=None, help="Use Eclair configuration file")
@click.option("--base-fee", default=0, help="Set base fee")
@click.option("--fee-rate", default=0, help="Set fee rate")
@click.option("--time_lock_delta", default=144, help="Set time lock delta")
@click.option("--fee-sigma", default=24, help="Fee sigma")
def suez(eclair_conf, base_fee, fee_rate, time_lock_delta, fee_sigma):
    if eclair_conf is None:
        ln = LndClient()
    else:
        from pyhocon import ConfigFactory
        config = ConfigFactory.parse_file(eclair_conf)
        password = config.get_string("eclair.api.password")
        try:
            port = config.get_int("eclair.api.port")
        except:
            port = 8080

        ln = EclairClient(port, password)

    table = Table(box=box.SIMPLE)
    table.add_column("inbound", justify="right")
    table.add_column("ratio", justify="center")
    table.add_column("outbound", justify="right")
    table.add_column("local\nfee", justify="right")
    table.add_column("remote\nfee", justify="right")
    table.add_column("uptime", justify="right")
    table.add_column("alias")

    total_inbound, total_outbound = 0, 0

    for c in sorted(
        ln.listchannels(),
        key=lambda x: int(x.local_balance_sat)
        / (x.local_balance_sat + x.remote_balance_sat),
    ):
        capacity, outbound, inbound = (
            c.capacity,
            c.local_balance_sat,
            c.remote_balance_sat,
        )
        send = int(20 * outbound / (outbound + inbound))
        recv = 20 - send
        bar = ("·" * recv) + "|" + ("·" * send)

        uptime = int(100 * c.uptime / c.lifetime)

        # set fee
        if base_fee and fee_rate:
            ratio = outbound / (outbound + inbound) - 0.5
            coef = math.exp(-fee_sigma * ratio * ratio)
            _fee_rate = 0.000001 * coef * fee_rate
            if _fee_rate < 0.000001:
                _fee_rate = 0.000001
            ln.updatechanpolicy(c, base_fee, _fee_rate, time_lock_delta)

        total_inbound += inbound
        total_outbound += outbound
        table.add_row(
            "{:,}".format(inbound),
            bar,
            "{:,}".format(outbound),
            str(c.fee_rate_local),
            str(c.fee_rate_remote),
            str(uptime),
            c.remote_alias,
        )

    table.add_row("-----------", "", "-----------")
    table.add_row("{:,}".format(total_inbound), "", "{:,}".format(total_outbound))

    console = Console()
    console.print(table)


if __name__ == "__main__":
    suez()

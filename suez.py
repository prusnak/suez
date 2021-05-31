#!/usr/bin/env python3
import subprocess
import json
import math

import click
from rich import box
from rich.console import Console
from rich.table import Table


class LnClient:
    def _run(self, *args):
        j = subprocess.run(("lncli",) + args, capture_output=True)
        return json.loads(j.stdout)

    def getinfo(self):
        return self._run("getinfo")

    def listchannels(self):
        return self._run("listchannels")["channels"]

    def getnodeinfo(self, node):
        return self._run("getnodeinfo", node)["node"]

    def getchaninfo(self, node):
        return self._run("getchaninfo", node)

    def updatechanpolicy(self, point, base, rate):
        return self._run(
            "updatechanpolicy",
            "--base_fee_msat",
            str(base),
            "--fee_rate",
            "%0.8f" % rate,
            "--time_lock_delta",
            "144",
            "--chan_point",
            point,
        )


@click.command()
@click.option("--set-base-fee", default=0, help="Set base fee")
@click.option("--set-fee-rate", default=0, help="Set fee rate")
@click.option("--fee-sigma", default=24, help="Fee sigma")
def suez(set_base_fee, set_fee_rate, fee_sigma):
    ln = LnClient()

    identity = ln.getinfo()["identity_pubkey"]

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
        key=lambda x: int(x["local_balance"])
        / (int(x["local_balance"]) + int(x["remote_balance"])),
    ):
        active, pubkey, point = c["active"], c["remote_pubkey"], c["channel_point"]
        capacity, outbound, inbound = (
            int(c["capacity"]),
            int(c["local_balance"]),
            int(c["remote_balance"]),
        )
        send = int(20 * outbound / (outbound + inbound))
        recv = 20 - send
        bar = ("·" * recv) + "|" + ("·" * send)

        uptime = int(100 * int(c["uptime"]) / int(c["lifetime"]))

        # set fee
        if set_base_fee and set_fee_rate:
            base_fee = set_base_fee
            ratio = outbound / (outbound + inbound) - 0.5
            coef = math.exp(-fee_sigma * ratio * ratio)
            fee_rate = 0.000001 * coef * set_fee_rate
            if fee_rate < 0.000001:
                fee_rate = 0.000001
            ln.updatechanpolicy(point, base_fee, fee_rate)

        # fees
        chan = ln.getchaninfo(c["chan_id"])
        if chan["node1_pub"] != identity:
            assert chan["node2_pub"] == identity
            fee_remote = chan["node1_policy"]["fee_rate_milli_msat"]
            fee_local = chan["node2_policy"]["fee_rate_milli_msat"]
        if chan["node2_pub"] != identity:
            assert chan["node1_pub"] == identity
            fee_local = chan["node1_policy"]["fee_rate_milli_msat"]
            fee_remote = chan["node2_policy"]["fee_rate_milli_msat"]

        # alias
        alias = ln.getnodeinfo(pubkey)["alias"]

        total_inbound += inbound
        total_outbound += outbound
        table.add_row(
            "{:,}".format(inbound),
            bar,
            "{:,}".format(outbound),
            str(fee_local),
            str(fee_remote),
            str(uptime),
            alias,
        )

    table.add_row("-----------", "", "-----------")
    table.add_row("{:,}".format(total_inbound), "", "{:,}".format(total_outbound))

    console = Console()
    console.print(table)


if __name__ == "__main__":
    suez()

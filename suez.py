from datetime import datetime
import math

import click
from rich import box
from rich.console import Console
from rich.table import Table

from lndclient import LndClient
from clnclient import ClnClient


class FeePolicy:
    def __init__(self, base_fee, fee_rate, fee_spread, time_lock_delta):
        self.base_fee = base_fee
        self.fee_rate = fee_rate
        self.fee_spread = fee_spread
        self.time_lock_delta = time_lock_delta

    def calculate(self, channel):
        ratio = channel.local_balance / (channel.capacity - channel.commit_fee)
        # -1.0 = all funds local
        # +1.0 = all funds remote
        ratio = 1.0 - 2.0 * ratio
        coef = math.exp(self.fee_spread * ratio)
        fee_rate = 0.000001 * coef * self.fee_rate
        if fee_rate < 0.000001:
            fee_rate = 0.000001
        base_fee = self.base_fee
        time_lock_delta = self.time_lock_delta
        return base_fee, fee_rate, time_lock_delta


def _sort_channels(c):
    return c.local_balance / (c.capacity - c.commit_fee)


def _since(ts):
    d = datetime.utcnow() - datetime.utcfromtimestamp(ts)
    return "%0.1f" % (d.total_seconds() / 86400)


@click.command()
@click.option("--base-fee", default=0, help="Set base fee.")
@click.option("--fee-rate", default=0, help="Set fee rate.")
@click.option("--fee-spread", default=0.0, help="Fee spread.")
@click.option("--time-lock-delta", default=40, help="Set time lock delta.")
@click.option(
    "--client",
    default="LND",
    type=click.Choice(("lnd", "c-lightning"), case_sensitive=False),
    help="Type of LN client.",
)
@click.option(
    "--client-args", default="", help="Extra arguments to pass to client RPC."
)
@click.option(
    "--show-remote-fees", is_flag=True, help="Show (estimate of) remote fees."
)
def suez(
    base_fee,
    fee_rate,
    fee_spread,
    time_lock_delta,
    client,
    client_args,
    show_remote_fees,
):
    clients = {
        "lnd": LndClient,
        "c-lightning": ClnClient,
    }

    ln = clients[client](client_args)

    if base_fee and fee_rate:
        policy = FeePolicy(base_fee, fee_rate, fee_spread, time_lock_delta)
        ln.apply_fee_policy(policy)
        ln.refresh()

    table = Table(box=box.SIMPLE)
    table.add_column("\ninbound", justify="right", style="bright_red")
    table.add_column("\nratio", justify="center")
    table.add_column("\noutbound", justify="right", style="green")
    table.add_column("local\nbase_fee\n(msat)", justify="right", style="bright_blue")
    table.add_column("local\nfee_rate\n(ppm)", justify="right", style="bright_blue")
    table.add_column("remote\nbase_fee\n(msat)", justify="right", style="bright_yellow")
    table.add_column("remote\nfee_rate\n(ppm)", justify="right", style="bright_yellow")
    table.add_column("uptime\n\n(%)", justify="right", style="bright_black")
    table.add_column("last\nforward\n(days)", justify="right")
    table.add_column("local\nfees\n(sat)", justify="right", style="bright_cyan")
    if show_remote_fees:
        table.add_column("remote\nfees\n(sat)", justify="right", style="bright_cyan")
    table.add_column("\nopener", justify="right")
    table.add_column("\nalias", max_width=25, no_wrap=True)

    total_local, total_remote, total_fees_local, total_fees_remote = 0, 0, 0, 0

    for c in sorted(ln.channels.values(), key=_sort_channels):
        send = int(round(10 * c.local_balance / (c.capacity - c.commit_fee)))
        recv = 10 - send
        bar = (
            "[bright_red]"
            + ("·" * recv)
            + "[/bright_red]"
            + "|"
            + "[green]"
            + ("·" * send)
            + "[/green]"
        )
        if c.uptime is not None and c.lifetime is not None:
            uptime = 100 * c.uptime // c.lifetime
        else:
            uptime = "n/a"
        total_fees_local += c.local_fees
        total_fees_remote += c.remote_fees
        total_local += c.local_balance
        total_remote += c.remote_balance
        columns = [
            "{:,}".format(c.remote_balance),
            bar,
            "{:,}".format(c.local_balance),
            str(c.local_base_fee),
            str(c.local_fee_rate),
            str(c.remote_base_fee),
            str(c.remote_fee_rate),
            str(uptime),
            _since(c.last_forward) if c.last_forward else "never",
            "{:,}".format(c.local_fees) if c.local_fees else "-",
        ]
        if show_remote_fees:
            columns += [
                "{:,}".format(c.remote_fees) if c.remote_fees else "-",
            ]
        columns += [
            "[bright_blue]local[/bright_blue]"
            if c.opener == "local"
            else "[bright_yellow]remote[/bright_yellow]",
            c.remote_alias,
        ]
        table.add_row(*columns)

    columns = ["─" * 10, None, "─" * 10, None, None, None, None, None, None, "─" * 7]
    if show_remote_fees:
        columns += ["─" * 7]
    table.add_row(*columns)
    columns = [
        "{:,}".format(total_remote),
        None,
        "{:,}".format(total_local),
        None,
        None,
        None,
        None,
        None,
        None,
        "{:,}".format(total_fees_local),
    ]
    if show_remote_fees:
        columns += [
            "{:,}".format(total_fees_remote),
        ]
    table.add_row(*columns)

    console = Console()
    console.print(table)

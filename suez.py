from datetime import datetime

import click
from rich import box, markup
from rich.console import Console
from rich.table import Table

from clnclient import ClnClient
from feepolicy import FeePolicy
from lndclient import LndClient
from score import Score


def _sort_channels(c):
    return c.local_balance / (c.capacity - c.commit_fee)


def _since(ts):
    d = datetime.utcnow() - datetime.utcfromtimestamp(ts)
    return "%0.1f" % (d.total_seconds() / 86400)


def info_box(ln, score):
    grid = Table.grid()
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("pubkey    : ", ln.local_pubkey)
    grid.add_row("alias     : ", ln.local_alias)
    grid.add_row("channels  : ", "%d" % len(ln.channels))
    if score is not None:
        node_score = score.get(ln.local_pubkey)
        node_score = "{:,}".format(node_score) if node_score is not None else "-"
        grid.add_row("score     : ", node_score)
    return grid


def channel_table(ln, score, show_remote_fees, show_chan_ids, excludes):
    table = Table(box=box.SIMPLE)
    table.add_column("\ninbound", justify="right", style="bright_red")
    table.add_column("\nratio", justify="center")
    table.add_column("\noutbound", justify="right", style="green")
    table.add_column("local\nbase_fee\n(msat)", justify="right", style="bright_blue")
    table.add_column("local\nfee_rate\n(ppm)", justify="right", style="bright_blue")
    table.add_column("remote\nbase_fee\n(msat)", justify="right", style="bright_yellow")
    table.add_column("remote\nfee_rate\n(ppm)", justify="right", style="bright_yellow")
    table.add_column("\nuptime\n(%)", justify="right")
    table.add_column("last\nforward\n(days)", justify="right")
    table.add_column("local\nfees\n(sat)", justify="right", style="bright_cyan")
    if show_remote_fees:
        table.add_column("remote\nfees\n(sat)", justify="right", style="bright_cyan")
    if score is not None:
        table.add_column("\nscore", justify="right")
    table.add_column("\nalias", max_width=25, no_wrap=True)
    if show_chan_ids:
        table.add_column("\nchan_id")

    total_local, total_fees_local = 0, 0
    total_remote, total_fees_remote = 0, 0
    local_base_fees, local_fee_rates = [], []
    remote_base_fees, remote_fee_rates = [], []

    for c in sorted(ln.channels.values(), key=_sort_channels):
        if c.chan_id in excludes:
            continue
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
        if c.uptime is not None and c.lifetime:
            uptime = 100 * c.uptime // c.lifetime
        else:
            uptime = "n/a"
        total_fees_local += c.local_fees
        total_fees_remote += c.remote_fees
        total_local += c.local_balance
        total_remote += c.remote_balance
        if c.local_base_fee is not None:
            local_base_fees.append(c.local_base_fee)
        if c.local_fee_rate is not None:
            local_fee_rates.append(c.local_fee_rate)
        if c.remote_base_fee is not None:
            remote_base_fees.append(c.remote_base_fee)
        if c.remote_fee_rate is not None:
            remote_fee_rates.append(c.remote_fee_rate)
        columns = [
            "{:,}".format(c.remote_balance),
            bar,
            "{:,}".format(c.local_balance),
            str(c.local_base_fee) if c.local_base_fee is not None else "-",
            str(c.local_fee_rate) if c.local_fee_rate is not None else "-",
            str(c.remote_base_fee) if c.remote_base_fee is not None else "-",
            str(c.remote_fee_rate) if c.remote_fee_rate is not None else "-",
            "[green]%s[/green]" % uptime
            if c.active
            else "[bright_red]%s[/bright_red]" % uptime,
            _since(c.last_forward) if c.last_forward else "never",
            "{:,}".format(c.local_fees) if c.local_fees else "-",
        ]
        if show_remote_fees:
            columns += [
                "{:,}".format(c.remote_fees) if c.remote_fees else "-",
            ]
        if score is not None:
            s = score.get(c.remote_node_id)
            columns += [
                "{:,}".format(s) if s is not None else "-",
            ]
        alias_color = "bright_blue" if c.opener == "local" else "bright_yellow"
        alias = c.remote_alias if c.remote_alias else c.remote_node_id[:16]
        columns += [
            "[%s]%s[/%s]" % (alias_color, markup.escape(alias), alias_color),
        ]
        if show_chan_ids:
            columns += [c.chan_id]
        table.add_row(*columns)

    columns = [
        "─" * 6,
        None,
        "─" * 6,
        "─" * 4,
        "─" * 4,
        "─" * 4,
        "─" * 4,
        None,
        None,
        "─" * 6,
    ]
    if show_remote_fees:
        columns += ["─" * 6]
    table.add_row(*columns)
    columns = [
        "{:,}".format(total_remote),
        None,
        "{:,}".format(total_local),
        format_average(local_base_fees),
        format_average(local_fee_rates),
        format_average(remote_base_fees),
        format_average(remote_fee_rates),
        None,
        None,
        "{:,}".format(total_fees_local),
    ]
    if show_remote_fees:
        columns += [
            "{:,}".format(total_fees_remote),
        ]
    table.add_row(*columns)
    return table

def format_average(fees):
    if len(fees) == 0:
        return None
    else:
        return "{}".format(sum(fees) // len(fees))

@click.command()
@click.option("--base-fee", default=0, help="Set base fee.")
@click.option("--fee-rate", default=0, help="Set fee rate.")
@click.option("--fee-spread", default=0.0, help="Fee spread.")
@click.option("--time-lock-delta", default=40, help="Set time lock delta.")
@click.option(
    "--client",
    default="lnd",
    type=click.Choice(("lnd", "c-lightning"), case_sensitive=False),
    help="Type of LN client.",
)
@click.option(
    "--client-args",
    default=[],
    multiple=True,
    help="Extra arguments to pass to client RPC.",
)
@click.option(
    "--show-remote-fees", is_flag=True, help="Show (estimate of) remote fees."
)
@click.option(
    "--show-scores", is_flag=True, help="Show node scores (from Lightning Terminal)."
)
@click.option("--show-chan-ids", is_flag=True, help="Show channel ids.")
@click.option(
    "--exclude",
    default=[],
    multiple=True,
    help="Exclude specific channel ids from the table.",
)
def suez(
    base_fee,
    fee_rate,
    fee_spread,
    time_lock_delta,
    client,
    client_args,
    show_remote_fees,
    show_scores,
    show_chan_ids,
    exclude,
):
    clients = {
        "lnd": LndClient,
        "c-lightning": ClnClient,
    }

    ln = clients[client](client_args)

    score = Score() if show_scores else None

    if len(ln.channels) == 0:
        click.echo("No channels found. Exiting")
        return

    if fee_rate:
        policy = FeePolicy(base_fee, fee_rate, fee_spread, time_lock_delta)
        ln.apply_fee_policy(policy)
        ln.refresh()

    info = info_box(ln, score)
    table = channel_table(ln, score, show_remote_fees, show_chan_ids, exclude)

    console = Console()
    console.print()
    console.print(info)
    console.print(table)

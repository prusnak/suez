from datetime import datetime

import click
from rich import box, markup
from rich.console import Console
from rich.table import Table

from clnclient import ClnClient
from feepolicy import FeePolicy
from lndcliclient import LndCliClient
from lndrestclient import LndRestClient
from terminal_web import TerminalWeb


def _sort_channels(c):
    return c.local_balance / (c.capacity - c.commit_fee)


def _since(ts):
    d = datetime.utcnow() - datetime.utcfromtimestamp(ts)
    return f"{d.total_seconds() / 86400:.1f}"


def _resolve_htlc(htlc_msat):
    if htlc_msat is None:
        return "-"
    htlc_sat = htlc_msat / 1000
    htlc_sat = int(htlc_sat) if htlc_sat == int(htlc_sat) else htlc_sat
    return f"{htlc_sat:,}"


def _resolve_disabled(c):
    local = "y" if c.local_disabled else "n" if c.local_disabled is not None else "-"
    remote = "y" if c.remote_disabled else "n" if c.remote_disabled is not None else "-"
    return f"[bright_blue]{local}[/bright_blue]|[bright_yellow]{remote}[/bright_yellow]"


def _resolve_good_peer(c, terminal_web):
    good_in = terminal_web.is_good_inbound_peer(c.remote_node_id)
    good_out = terminal_web.is_good_outbound_peer(c.remote_node_id)
    res_in = "[green]y[/green]" if good_in else "[bright_red]n[/bright_red]"
    res_out = "[green]y[/green]" if good_out else "[bright_red]n[/bright_red]"
    return res_in + "|" + res_out


def info_box(ln, terminal_web):
    grid = Table.grid()
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row("pubkey    : ", ln.local_pubkey)
    grid.add_row("alias     : ", ln.local_alias)
    grid.add_row("channels  : ", f"{len(ln.channels):,}")
    if terminal_web.show_scores:
        score = terminal_web.get_score(ln.local_pubkey)
        score = f"{score:,}" if score is not None else "-"
        grid.add_row("score     : ", score)
    return grid


def channelcount_info_box(count, channel_type):
    grid = Table.grid()
    grid.add_column(style="bold")
    grid.add_column()
    grid.add_row(f"{channel_type} channels : ", f"{count}")
    return grid


def channel_table(
    channels,
    terminal_web,
    show_remote_fees,
    show_chan_ids,
    show_forwarding_stats,
    show_minmax_htlc,
    show_disabled,
):
    table = Table(box=box.SIMPLE)
    table.add_column("\ninbound", justify="right", style="bright_red")
    table.add_column("\nratio", justify="center")
    table.add_column("\noutbound", justify="right", style="green")
    if show_disabled:
        table.add_column("is\ndisabled", justify="right")
    if show_minmax_htlc:
        table.add_column("local\nmin_htlc\n(sat)", justify="right", style="bright_blue")
        table.add_column("local\nmax_htlc\n(sat)", justify="right", style="bright_blue")
        table.add_column(
            "remote\nmin_htlc\n(sat)", justify="right", style="bright_yellow"
        )
        table.add_column(
            "remote\nmax_htlc\n(sat)", justify="right", style="bright_yellow"
        )
    table.add_column("local\nbase_fee\n(msat)", justify="right", style="bright_blue")
    table.add_column("local\nfee_rate\n(ppm)", justify="right", style="bright_blue")
    table.add_column("remote\nbase_fee\n(msat)", justify="right", style="bright_yellow")
    table.add_column("remote\nfee_rate\n(ppm)", justify="right", style="bright_yellow")
    table.add_column("\nuptime\n(%)", justify="right")
    table.add_column("last\nforward\n(days)", justify="right")
    table.add_column("local\nfees\n(sat)", justify="right", style="bright_cyan")
    if show_forwarding_stats:
        table.add_column("\nfwd in", justify="right")
        table.add_column("\nin %", justify="right")
        table.add_column("\nfwd out", justify="right")
        table.add_column("\nout %", justify="right")
    if show_remote_fees:
        table.add_column("remote\nfees\n(sat)", justify="right", style="bright_cyan")
    if terminal_web.show_good_peers:
        table.add_column("good\npeer\n(in|out)", justify="right")
    if terminal_web.show_scores:
        table.add_column("\nscore", justify="right")
    table.add_column("\nalias", max_width=25, no_wrap=True)
    if show_chan_ids:
        table.add_column("\nchan_id")

    total_local, total_fees_local = 0, 0
    total_remote, total_fees_remote = 0, 0
    local_base_fees, local_fee_rates = [], []
    remote_base_fees, remote_fee_rates = [], []

    for c in sorted(channels, key=_sort_channels):
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
        total_fees_local += c.local_fees_msat
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
            f"{c.remote_balance:,}",
            bar,
            f"{c.local_balance:,}",
        ]
        if show_disabled:
            columns += [
                _resolve_disabled(c),
            ]
        if show_minmax_htlc:
            columns += [
                _resolve_htlc(c.local_min_htlc),
                _resolve_htlc(c.local_max_htlc),
                _resolve_htlc(c.remote_min_htlc),
                _resolve_htlc(c.remote_max_htlc),
            ]
        columns += [
            str(c.local_base_fee) if c.local_base_fee is not None else "-",
            str(c.local_fee_rate) if c.local_fee_rate is not None else "-",
            str(c.remote_base_fee) if c.remote_base_fee is not None else "-",
            str(c.remote_fee_rate) if c.remote_fee_rate is not None else "-",
            f"[green]{uptime}[/green]"
            if c.active
            else f"[bright_red]{uptime}[/bright_red]",
            _since(c.last_forward) if c.last_forward else "never",
            f"{round(c.local_fees_msat / 1000):,}"
            if c.local_fees_msat
            else "-",
        ]
        if show_forwarding_stats:
            columns += [
                f"{c.ins}",
                f"{c.ins_percent:.0%}",
                f"{c.outs}"
                f"{c.outs_percent:.0%}",
            ]
        if show_remote_fees:
            columns += [
                f"{c.remote_fees:,}" if c.remote_fees else "-",
            ]
        if terminal_web.show_good_peers:
            columns += [
                _resolve_good_peer(c, terminal_web),
            ]
        if terminal_web.show_scores:
            s = terminal_web.get_score(c.remote_node_id)
            columns += [
                f"{s:,}" if s is not None else "-",
            ]
        alias_color = "bright_blue" if c.opener == "local" else "bright_yellow"
        alias = c.remote_alias if c.remote_alias else c.remote_node_id[:16]
        columns += [
            f"[{alias_color}]{markup.escape(alias)}[/{alias_color}]",
        ]
        if show_chan_ids:
            columns += [c.chan_id]
        table.add_row(*columns)

    columns = [
        "─" * 6,
        None,
        "─" * 6,
    ]
    if show_disabled:
        columns += [
            None,
        ]
    if show_minmax_htlc:
        columns += [
            None,
            None,
            None,
            None,
        ]
    columns += [
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
        f"{total_remote:,}",
        None,
        f"{total_local:,}",
    ]
    if show_disabled:
        columns += [
            None,
        ]
    if show_minmax_htlc:
        columns += [
            None,
            None,
            None,
            None,
        ]
    columns += [
        f"{sum(local_base_fees) // len(local_base_fees)}",
        f"{sum(local_fee_rates) // len(local_fee_rates)}",
        f"{sum(remote_base_fees) // len(remote_base_fees)}",
        f"{sum(remote_fee_rates) // len(remote_fee_rates)}",
        None,
        None,
        f"{round(total_fees_local / 1000):,}",
    ]
    if show_remote_fees:
        columns += [
            f"{total_fees_remote:,}",
        ]
    table.add_row(*columns)
    return table


@click.command()
@click.option("--base-fee", default=0, help="Set base fee.")
@click.option("--fee-rate", default=0, help="Set fee rate.")
@click.option("--fee-spread", default=0.0, help="Fee spread.")
@click.option("--time-lock-delta", default=40, help="Set time lock delta.")
@click.option(
    "--client",
    default="lnd",
    type=click.Choice(("lnd", "c-lightning", "lnd-rest"), case_sensitive=False),
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
@click.option(
    "--show-good-peers", is_flag=True, help="Show good peers (from Lightning Terminal)."
)
@click.option("--show-chan-ids", is_flag=True, help="Show channel ids.")
@click.option(
    "--show-forwarding-stats",
    is_flag=True,
    help="Show forwarding counts and success percentages (CLN)",
)
@click.option("--show-minmax-htlc", is_flag=True, help="Show min and max htlc.")
@click.option("--show-disabled", is_flag=True, help="Show if channel is disabled.")
@click.option(
    "--channels",
    default="all",
    type=click.Choice(("all", "public", "private", "split"), case_sensitive=False),
    help="Which channels to select/show.",
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
    show_good_peers,
    show_chan_ids,
    show_forwarding_stats,
    show_minmax_htlc,
    show_disabled,
    channels,
):
    clients = {
        "lnd": LndCliClient,
        "c-lightning": ClnClient,
        "lnd-rest": LndRestClient,
    }

    ln = clients[client](client_args)

    if len(ln.channels) == 0:
        click.echo("No channels found. Exiting")
        return

    terminal_web = TerminalWeb(ln.local_pubkey, show_scores, show_good_peers)

    if fee_rate:
        policy = FeePolicy(base_fee, fee_rate, fee_spread, time_lock_delta)
        ln.apply_fee_policy(policy)
        ln.refresh()

    info = info_box(ln, terminal_web)

    console = Console()
    console.print()
    console.print(info)

    if channels == "split":
        public_channels = [c for c in ln.channels.values() if not c.private]
        private_channels = [c for c in ln.channels.values() if c.private]

        if len(public_channels) > 0:
            public_table = channel_table(
                public_channels,
                terminal_web,
                show_remote_fees,
                show_chan_ids,
                show_forwarding_stats,
                show_minmax_htlc,
                show_disabled,
            )
            public_info = channelcount_info_box(len(public_channels), "public")
            console.print(public_table)
            console.print(public_info)

        if len(private_channels) > 0:
            private_table = channel_table(
                private_channels,
                terminal_web,
                show_remote_fees,
                show_chan_ids,
                show_forwarding_stats,
                show_minmax_htlc,
                show_disabled,
            )
            private_info = channelcount_info_box(len(private_channels), "private")
            console.print(private_table)
            console.print(private_info)
        console.print()

    else:
        if channels == "public":
            show_channels = [c for c in ln.channels.values() if not c.private]
        elif channels == "private":
            show_channels = [c for c in ln.channels.values() if c.private]
        else:  # all
            show_channels = ln.channels.values()

        if len(show_channels) > 0:
            table = channel_table(
                show_channels,
                terminal_web,
                show_remote_fees,
                show_chan_ids,
                show_forwarding_stats,
                show_minmax_htlc,
                show_disabled,
            )
            console.print(table)

# Suez

Tool for pretty printing and optimizing Lightning Network channels.

![screenshot](screenshot.png)

## Installation

1. Install [poetry](https://python-poetry.org/)
2. `poetry install`
3. `poetry run python ./suez`

## Channel fee policy

You can override the channel fee policy by changing the `FeePolicy` class.
Example implementation sets exponentially higher fees for channels with lower local balance than half of the channel capacity.
The steepness is controlled via the `fee_sigma` argument.

## Lightning node support

Currently, Suez supports LND and C-Lightning.
By default it uses LND (`lncli`).
You can use it with C-Lightning as follows:

`poetry run python ./suez --client=C-Lightning`

If you need to pass additional options to the lncli/lightning-cli you can do so:

`poetry run python ./suez --client=C-Lightning --client-args=--conf=/usr/local/etc/lightningd-bitcoin.conf`

Adding support requires writing a client similar to lndclient.py and instantiating it in suez.py.

## Donate

You can tip me some satoshis via [tippin.me/@pavolrusnak](https://tippin.me/@pavolrusnak)

## License

This software is licensed under the [GNU General Public License v3](COPYING).

# Suez

Tool for pretty printing and optimizing Lightning Network channels.

![screenshot](screenshot.png)

## Installation

1. Install [poetry](https://python-poetry.org/)
2. `poetry install`
3. `poetry run ./suez`

## Channel fee policy

You can override the channel fee policy by changing the `FeePolicy` class.

Example implementation does the following:

* sets lower fees for channels with mostly local balance
* sets higher fees for channels with mostly remote balance
* sets medium fees for balanced channels

You control the spread via the `fee-spread` argument.

## Lightning node support

Currently, Suez supports LND and C-Lightning.
By default it uses LND (`lncli`).
You can use it with C-Lightning as follows:

`poetry run ./suez --client=C-Lightning`

If you need to pass additional options to the lncli/lightning-cli you can do so:

`poetry run ./suez --client=C-Lightning --client-args=--conf=/usr/local/etc/lightningd-bitcoin.conf`

Adding support requires writing a client similar to lndclient.py and instantiating it in suez.py.

## Donate

You can tip me some satoshis via [tippin.me/@pavolrusnak](https://tippin.me/@pavolrusnak)

## License

This software is licensed under the [GNU General Public License v3](COPYING).

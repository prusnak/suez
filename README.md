# Suez

Tool for pretty printing and optimizing Lightning Network channels.

![screenshot](screenshot.png)

## Channel fee policy

You can override the channel fee policy by changing the `FeePolicy`.
Example implementation sets higher fees for balanced channels and lower fees for unbalanced ones.

## Lightning node support

Currently, Suez only supports LND, but adding support for c-lightning and Eclair should be trivial.

## License

This software is licensed under the [GNU General Public License v3](COPYING).

# goxsh

goxsh — a command-line frontend to the Mt. Gox Bitcoin Exchange with support for Exchange Bitcoins.

## Features

- Buy and sell bitcoins
- Specify buy/sell amounts in BTC or USD
- List and cancel orders
- Withdraw bitcoins (Mt. Gox only)
- Interactive authentication with no-echo password prompt — no need to store your credentials on disk
- Login to one of two exchanges (login user@mtgox or login user@exchb)
- Display account balance
- Display ticker
- Calculate profitable short/long prices from an initial price
- Tab completion of commands
- Abort commands with SIGINT (ctrl-c on *nix) without exiting, if Mt. Gox is being slow

## Requirements

[Python](http://python.org/) 2.6 or a newer 2.* release.

## Usage

Run the script in a terminal window and type "help" to see the list of available commands.

## License

Public domain. :)
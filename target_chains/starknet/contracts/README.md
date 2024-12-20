# Pyth Starknet Contract

This directory contains the Pyth contract on [Starknet](https://www.starknet.io/).

## Installation

1. Install Scarb (the Cairo and Starknet development toolchain) by following [the installation instructions](https://docs.swmansion.com/scarb/download).
2. Install Starknet Foundry by following [the installation instructions](https://foundry-rs.github.io/starknet-foundry/getting-started/installation.html).

The `.tool-versions` file in this directory specifies the tool versions used by the contract.

## Testing

Run `snforge test` in this directory to run the contract unit tests and integration tests.

## Local deployment

1. Install Starkli (a cli tool for Starknet) by following [the installation instructions](https://github.com/xJonathanLEI/starkli).
2. Install Katana (a local Starknet node) by following [the installation instructions](https://book.starknet.io/ch02-04-katana.html).
3. Run the `deploy/local_deploy` setup script.

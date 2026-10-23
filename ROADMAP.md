# Aw-Shell Roadmap

What's coming to Aw-Shell, roughly in order.

## Next up

### Nix support ❄️

Install and configure Aw-Shell on NixOS the Nix way: try it with a single `nix run`, or add it to your Home Manager config and set the shell's options there.

- **Why:** NixOS users currently have no supported way to install Aw-Shell. The original Ax-Shell had community Nix support, so there's demand.
- **Starting point:** [poogas/Ax-Shell](https://github.com/poogas/Ax-Shell), the Ax-Shell fork that added a flake and a Home Manager module. Aw-Shell has changed a lot since, so it's a reference, not a copy.
- **Done when:** `nix run` starts the shell, Home Manager can install and configure it, and the README has a NixOS section.

## Later

Nothing here yet.

## Done

Released work is listed in `version.json` and shown in the in-app updater.

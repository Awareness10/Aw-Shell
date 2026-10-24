# Aw-Shell Roadmap

What's coming to Aw-Shell, roughly in order.

## Next up

### Publish to the AUR 📦

Install Aw-Shell like any other Arch package: `paru -S aw-shell` instead of a curl-to-bash script, with updates through your AUR helper.

- **Why:** a package is easier to install, update and remove, and shows exactly what it depends on. It also needs a cleaner layout: the app's code lives outside `~/.config`, and `~/.config/aw-shell` holds only your settings, so dotfile managers and resets don't touch the app.
- **Starting point:** redesign where Aw-Shell keeps its code, settings and generated files, with a migration for existing installs in `~/.config/aw-shell`. Keep the Nix package in mind, since it has the same needs.
- **Done when:** `aw-shell` is on the AUR, existing installs move over without losing settings, and the README installs from the AUR.

### Nix support ❄️

Install and configure Aw-Shell on NixOS the Nix way: try it with a single `nix run`, or add it to your Home Manager config and set the shell's options there.

- **Why:** NixOS users currently have no supported way to install Aw-Shell. The original Ax-Shell had community Nix support, so there's demand.
- **Starting point:** [poogas/Ax-Shell](https://github.com/poogas/Ax-Shell), the Ax-Shell fork that added a flake and a Home Manager module. Aw-Shell has changed a lot since, so it's a reference, not a copy.
- **Done when:** `nix run` starts the shell, Home Manager can install and configure it, and the README has a NixOS section.

## Later

Nothing here yet.

## Done

Released work is listed in `version.json` and shown in the in-app updater.

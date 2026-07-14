# Pane Layouts Plugin Design

## Goal

Move Herdr pane geometry behavior out of machine dotfiles into a portable, focused plugin. Dotfiles retain only the user's key choices.

## Scope

The `layouts` plugin exposes six actions:

- equalize the current tab into vertical columns;
- cycle through even vertical, even horizontal, main-left, main-top, and tiled layouts;
- resize the current pane left, down, up, or right by two percent.

Smart Rename remains separate because naming and pane geometry have unrelated responsibilities.

## Architecture

`herdr-plugin.toml` declares fixed actions. Resize actions call Herdr's CLI directly. Equalize and cycle invoke one Python stdlib script that communicates with Herdr's Unix socket.

The layout script preserves running processes by moving non-anchor panes into a temporary staging tab and reinserting them according to a target layout tree. On failure, it attempts to recover staged panes into the original tab. It refuses to reshape zoomed tabs.

## Migration

1. Link and validate the plugin.
2. Replace dotfiles shell bindings with `plugin_action` bindings.
3. Verify action resolution and live behavior.
4. Remove the old installed/script source only after verification.

## Testing

Unit tests cover balanced trees, preset uniqueness, insertion order, and single-pane behavior. Python compilation and TOML parsing catch syntax errors. Live verification covers one resize and one reversible layout action.

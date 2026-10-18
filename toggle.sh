#!/bin/sh
# Optional first argv is a literal launcher path, never a shell command.
if [ -n "${1:-}" ]; then
    if [ -f "$1" ] && [ -x "$1" ]; then
        exec "$1" --toggle
    fi
    printf '%s\n' "Configured Gentle Dot appPath is not an executable file: $1. Set appPath to the native launcher or clear it for automatic lookup." >&2
    exit 127
fi

# Source installs are not necessarily included in the shell's PATH.
if [ -n "${HOME:-}" ] && [ -x "$HOME/.local/bin/gentle-dot" ]; then
    exec "$HOME/.local/bin/gentle-dot" --toggle
fi

if command -v gentle-dot >/dev/null 2>&1; then
    exec gentle-dot --toggle
fi

printf '%s\n' 'Gentle Dot is not installed or executable. Install the official app first.' >&2
exit 127

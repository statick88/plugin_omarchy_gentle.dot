#!/bin/sh
# Usage: /bin/sh scripts/build-native.sh [--build-reviewed-installer]
# First run downloads/retains rustup-init.sh and stops. Inspect that file before
# rerunning with --build-reviewed-installer. No sudo, profile edits, or app launch.
set -eu
umask 077
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
INSTALL="$ROOT/.gentle-dot-install"
SOURCE="$ROOT/vendor/gentle-dot"
case "${1:-}" in
    '') BUILD=0 ;;
    --build-reviewed-installer) BUILD=1 ;;
    *) printf '%s\n' 'Usage: /bin/sh scripts/build-native.sh [--build-reviewed-installer]' >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || exit 2
NODE=$(command -v node)
NODE_DIR=$(dirname -- "$NODE")
export HOME="$INSTALL/home" TMPDIR="$INSTALL/tmp" TMP="$INSTALL/tmp" TEMP="$INSTALL/tmp"
export XDG_CONFIG_HOME="$INSTALL/config" XDG_DATA_HOME="$INSTALL/share"
export XDG_CACHE_HOME="$INSTALL/cache" XDG_STATE_HOME="$INSTALL/state"
export CARGO_HOME="$INSTALL/cargo" RUSTUP_HOME="$INSTALL/rustup"
export PNPM_HOME="$INSTALL/pnpm" npm_config_cache="$INSTALL/cache/npm"
export npm_config_store_dir="$INSTALL/cache/pnpm" npm_config_manage_package_manager_versions=false
export npm_config_userconfig="$INSTALL/config/npm-user.rc" npm_config_globalconfig="$INSTALL/config/npm-global.rc"
export PATH="$INSTALL/npm/bin:$CARGO_HOME/bin:$NODE_DIR:/usr/bin:/bin"
export CARGO_TARGET_DIR="$SOURCE/apps/desktop/src-tauri/target"
mkdir -p "$HOME" "$TMPDIR" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$XDG_STATE_HOME"
# npm rejects loading the same file as both user and global configuration.
: > "$npm_config_userconfig"
: > "$npm_config_globalconfig"
[ "$(git -C "$SOURCE" rev-parse HEAD)" = 8cb20ee888c88be2b359258a65499c20b59e2a86 ] || {
    printf '%s\n' 'Unexpected vendor/gentle-dot revision; refusing to build.' >&2; exit 1;
}
node -e 'if (+process.versions.node.split(".")[0] < 24) process.exit(1)'
INSTALLER="$INSTALL/rustup-init.sh"
if [ "$BUILD" = 0 ]; then
    # Keep the exact reviewed installer; never replace it on a subsequent build.
    if [ ! -f "$INSTALLER" ]; then
        curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' --tlsv1.2 \
            https://sh.rustup.rs -o "$INSTALLER.download"
        /bin/sh -n "$INSTALLER.download"
        mv -- "$INSTALLER.download" "$INSTALLER"
    fi
    sha256sum "$INSTALLER"
    printf 'Inspect %s, then run:\n/bin/sh "%s/scripts/build-native.sh" --build-reviewed-installer\n' "$INSTALLER" "$ROOT"
    exit 0
fi
[ -f "$INSTALLER" ] || { printf '%s\n' 'Run without arguments and inspect the retained installer first.' >&2; exit 1; }
/bin/sh -n "$INSTALLER"
export RUSTUP_DIST_SERVER=https://static.rust-lang.org RUSTUP_UPDATE_ROOT=https://static.rust-lang.org/rustup
if [ ! -x "$CARGO_HOME/bin/rustc" ]; then
    /bin/sh "$INSTALLER" -y --profile minimal --no-modify-path --default-toolchain stable
fi
export RUSTUP_TOOLCHAIN=stable
[ "$(rustc --version | cut -d . -f 2)" -ge 90 ] || {
    printf '%s\n' 'Upstream requires Rust 1.90 or newer; update the local stable toolchain.' >&2; exit 1;
}
if [ ! -x "$INSTALL/npm/bin/pnpm" ]; then
    npm install --global --prefix "$INSTALL/npm" --registry=https://registry.npmjs.org pnpm@11.5.0
fi
[ "$(pnpm --version)" = 11.5.0 ] || exit 1
cd "$SOURCE"
pnpm install --frozen-lockfile
pnpm build
pnpm --filter @gentle-dot/desktop tauri build --no-bundle
[ -x "$CARGO_TARGET_DIR/release/gentle-dot" ]
printf '%s\n' "$PATH" > "$INSTALL/runtime-path"
{ node --version; pnpm --version; rustc --version; cargo --version; } > "$INSTALL/toolchain-versions"
printf '%s\n' 'Native build ready. Retain vendor/gentle-dot and .gentle-dot-install; app not launched.'

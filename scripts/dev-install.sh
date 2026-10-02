#!/bin/sh
# Links the files MintToys installs outside Python, for now the panel icons, from this
# checkout into ~/.local/share, where the desktop finds them by name, as it will once the
# package is installed. Links rather than copies, so the checkout stays the only version.
#
#   sh scripts/dev-install.sh            link them
#   sh scripts/dev-install.sh --remove   take the links out again
#
# Restart the panel icon afterwards (python3 -m minttoys.tray) so it asks for the icons by
# name again.

set -eu

checkout=$(cd "$(dirname "$0")/.." && pwd)
data=${XDG_DATA_HOME:-$HOME/.local/share}
remove=0
[ "${1:-}" = "--remove" ] && remove=1

for source in "$checkout"/data/icons/hicolor/*/apps/*; do
  relative=${source#"$checkout/data/"}
  target="$data/$relative"
  if [ "$remove" = 1 ]; then
    if [ -L "$target" ]; then
      rm "$target"
      echo "removed: $target"
    fi
  else
    mkdir -p "$(dirname "$target")"
    ln -sfn "$source" "$target"
    echo "linked:  $target"
  fi
done

# A changed directory is what tells running programs to look at the icons again.
[ -d "$data/icons/hicolor" ] && touch "$data/icons/hicolor"

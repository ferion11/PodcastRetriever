#!/bin/sh

# common shell emulators: xterm, rxvt, konsole, kvt, gnome-terminal, nxterm, eterm.

terminal='xterm'

tty -s || { "$terminal" -e "$0" "$@"; exit 0; }

./python/PodcastRetriever.py --keep "$@"

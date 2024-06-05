#!/usr/bin/env bash

SESSIONNAME="UE"
tmux start-server

# create a session with five panes
tmux new-session -d -s ${SESSIONNAME} -n Shell1 -d "/usr/bin/env sh -c \"echo 'first shell'\"; /usr/bin/env sh -i"
tmux split-window -t ${SESSIONNAME}:0 "/usr/bin/env sh -c \"echo 'second shell'\"; /usr/bin/env sh -i"
tmux split-window -t ${SESSIONNAME}:0 "/usr/bin/env sh -c \"echo 'third shell'\"; /usr/bin/env sh -i"
tmux split-window -t ${SESSIONNAME}:0 "/usr/bin/env sh -c \"echo 'fourth shell'\"; /usr/bin/env sh -i"
tmux split-window -t ${SESSIONNAME}:0 "/usr/bin/env sh -c \"echo 'fifth shell'\"; /usr/bin/env sh -i"

# change layout to tiled
tmux select-layout -t ${SESSIONNAME}:0 tiled

tmux attach -t${SESSIONNAME}


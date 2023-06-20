#!/usr/bin/env sh

tmux start-server

# create a session with five panes
tmux new-session -d -s MySession -n Shell1 -d "/usr/bin/env sh -c \"echo 'first shell'\"; /usr/bin/env sh -i"
tmux split-window -t MySession:0 "/usr/bin/env sh -c \"echo 'second shell'\"; /usr/bin/env sh -i"
tmux split-window -t MySession:0 "/usr/bin/env sh -c \"echo 'third shell'\"; /usr/bin/env sh -i"
tmux split-window -t MySession:0 "/usr/bin/env sh -c \"echo 'fourth shell'\"; /usr/bin/env sh -i"
tmux split-window -t MySession:0 "/usr/bin/env sh -c \"echo 'fifth shell'\"; /usr/bin/env sh -i"

# change layout to tiled
tmux select-layout -t MySession:0 tiled

tmux attach -tMySession


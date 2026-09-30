# Render build fix

This version prevents Render from compiling dlib from source. It installs the prebuilt Linux `dlib-bin` wheel with `--only-binary=:all:` and installs `face-recognition` without dependency resolution.

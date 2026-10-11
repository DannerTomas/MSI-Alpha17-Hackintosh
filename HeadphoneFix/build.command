#!/bin/zsh
set -euo pipefail
source_dir=${0:A:h}
/usr/bin/xcrun clang -arch x86_64 -O2 -Wall -Wextra -Werror \
    -framework IOKit -framework CoreFoundation \
    "$source_dir/src/alc274-headphones.c" \
    -o "$source_dir/bin/alc274-headphones"
print '编译完成。'

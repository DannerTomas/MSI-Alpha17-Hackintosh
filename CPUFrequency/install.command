#!/bin/zsh
set -eu
package_dir=${0:A:h}
if ! /usr/bin/xcode-select -p >/dev/null 2>&1; then
    print -u2 '需要 Apple Command Line Tools 提供 Python 3；请先运行 xcode-select --install。'
    exit 1
fi
if [[ $# -eq 1 && "$1" == --check ]]; then
    exec /usr/bin/python3 -I "$package_dir/install.py" --check
fi
if [[ $# -ne 0 ]]; then
    print -u2 '用法：install.command [--check]'
    exit 1
fi
/usr/bin/python3 -I "$package_dir/install.py" --check
exec /usr/bin/sudo /usr/bin/python3 -I "$package_dir/install.py"

#!/bin/zsh
set -euo pipefail

runtime="$HOME/Library/Application Support/ALC274HeadphoneFix"
agent="$HOME/Library/LaunchAgents/local.alc274-headphones.plist"
uid_value=$(/usr/bin/id -u)
label=local.alc274-headphones
[[ ! -L "$runtime" && ! -L "$agent" ]]

/bin/launchctl disable "gui/$uid_value/$label"
/bin/launchctl bootout "gui/$uid_value/$label" >/dev/null 2>&1 || true
if [[ -x "$runtime/alc274-headphones" ]]; then
    "$runtime/alc274-headphones" --restore-original || print -u2 '当前声卡接口不可用，未恢复节点；重启后由原驱动初始化。'
fi
archive="${runtime}.disabled-$(/bin/date +%Y%m%d-%H%M%S)"
if [[ -d "$runtime" ]]; then
    /bin/mv "$runtime" "$archive"
else
    /bin/mkdir -p "$archive"
fi
if [[ -f "$agent" ]]; then
    /bin/mv "$agent" "$archive/LaunchAgent.plist"
fi
print "耳机自动修复已停用，文件已保留在：$archive"

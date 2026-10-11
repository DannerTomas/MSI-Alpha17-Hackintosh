#!/bin/zsh
set -euo pipefail

source_dir=${0:A:h}
runtime="$HOME/Library/Application Support/ALC274HeadphoneFix"
agent="$HOME/Library/LaunchAgents/local.alc274-headphones.plist"
logs="$HOME/Library/Logs/ALC274HeadphoneFix"
uid_value=$(/usr/bin/id -u)
label=local.alc274-headphones

[[ -x "$source_dir/bin/alc274-headphones" && -r "$source_dir/src/alc274-headphones.c" ]]
[[ ! -L "$runtime" && ! -L "$agent" && ! -L "$logs" ]]
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != --check ) ]]; then
    print -u2 '用法：install.command [--check]'
    exit 2
fi

tmp_dir=$(/usr/bin/mktemp -d)
trap '/bin/rm -f "$tmp_dir/agent.plist"; /bin/rmdir "$tmp_dir"' EXIT
/bin/cp "$source_dir/LaunchAgent.plist" "$tmp_dir/agent.plist"
/usr/bin/plutil -replace ProgramArguments.0 -string "$runtime/alc274-headphones" "$tmp_dir/agent.plist"
/usr/bin/plutil -replace StandardOutPath -string "$logs/stdout.log" "$tmp_dir/agent.plist"
/usr/bin/plutil -replace StandardErrorPath -string "$logs/stderr.log" "$tmp_dir/agent.plist"
/usr/bin/plutil -lint "$tmp_dir/agent.plist"

if [[ ${1:-} == --check ]]; then
    print '安装文件与启动项检查通过；未修改已安装程序。'
    exit 0
fi

umask 077
stamp=$(/bin/date +%Y%m%d-%H%M%S)
if [[ -d "$runtime" ]] && ! /usr/bin/cmp -s "$source_dir/bin/alc274-headphones" "$runtime/alc274-headphones"; then
    /usr/bin/ditto "$runtime" "${runtime}.backup-${stamp}"
fi
/bin/mkdir -p "$runtime" "${agent:h}" "$logs"
if [[ -f "$agent" ]]; then
    /bin/cp "$agent" "$runtime/LaunchAgent-before-${stamp}.plist"
fi
/bin/launchctl bootout "gui/$uid_value/$label" >/dev/null 2>&1 || true
/usr/bin/install -m 755 "$source_dir/bin/alc274-headphones" "$runtime/alc274-headphones"
/usr/bin/install -m 644 "$source_dir/src/alc274-headphones.c" "$runtime/alc274-headphones.c"
/usr/bin/install -m 644 "$tmp_dir/agent.plist" "$agent"
/usr/bin/touch "$logs/stdout.log" "$logs/stderr.log"
/bin/chmod 600 "$logs/stdout.log" "$logs/stderr.log"
/bin/launchctl enable "gui/$uid_value/$label"
/bin/launchctl bootstrap "gui/$uid_value" "$agent"
print '耳机自动修复已安装，登录后自动运行。'
print '程序需要当前 EFI 中的 alc-verbs 接口；插拔后最多等待约 2 秒。'

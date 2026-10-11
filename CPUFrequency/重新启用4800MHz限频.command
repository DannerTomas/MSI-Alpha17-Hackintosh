#!/bin/zsh
set -eu
/usr/bin/sudo -v
/usr/bin/sudo /bin/launchctl enable system/local.ryzen-4800
if ! /usr/bin/sudo /bin/launchctl print system/local.ryzen-4800 >/dev/null 2>&1; then
    /usr/bin/sudo /bin/launchctl bootstrap system /Library/LaunchDaemons/local.ryzen-4800.plist
fi
/usr/bin/sudo /bin/launchctl kickstart system/local.ryzen-4800
print '4800 MHz 限频自动应用服务已启用。'

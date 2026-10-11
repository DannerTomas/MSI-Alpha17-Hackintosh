#!/bin/zsh
set -eu
/usr/bin/sudo -v
/usr/bin/sudo /bin/launchctl disable system/local.ryzen-4800
if /usr/bin/sudo /bin/launchctl print system/local.ryzen-4800 >/dev/null 2>&1; then
    /usr/bin/sudo /bin/launchctl bootout system/local.ryzen-4800
fi
/usr/bin/sudo /usr/bin/python3 -I /Library/PrivilegedHelperTools/local.ryzen-4800/ryzen_4800.py restore
print '自动限频已停用；已向 CPU 恢复本次设置前的 5450 MHz 上限。'

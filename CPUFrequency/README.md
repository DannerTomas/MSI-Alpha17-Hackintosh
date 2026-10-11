# CPU 4800 MHz 限频

适用于本机 Ryzen 9 7945HX。设置最高睿频目标为 4800 MHz，保留动态降频与 16 核 32 线程，不修改电压、功耗限制或 EFI。

- 双击 `install.command`，输入管理员密码安装。开机及每 30 秒自动维护一次；已有相同安装时保留当前启停状态。
- `一键查看CPU逐核频率.command`：查看 16 个物理核心、每核两个 SMT 线程的采样频率，Control+C 退出。
- `关闭限频并恢复原值.command`：停用自动服务，恢复本机设置前查询到的 5450 MHz 上限。
- `重新启用4800MHz限频.command`：重新启用 4800 MHz 限频。

需要 Apple Command Line Tools 提供的 `/usr/bin/python3`，缺少时先运行 `xcode-select --install`。沿用配套 EFI 的 `debug=0x100`，无需新增内核驱动。仅执行检查可运行 `./install.command --check`，不会写入 CPU 设置。

附带现用 Python 源码、LaunchDaemon 配置及原始频率记录。服务安装在 `/Library/PrivilegedHelperTools/local.ryzen-4800/`，状态记录为 `/var/run/ryzen-4800-status.json`。

频率显示来自 `powermetrics` 的一秒平均值，并非瞬时峰值。短时测试主要为 4.78～4.80 GHz，曾出现约 4.826 GHz 的读数，不能保证任意瞬间严格不超过 4800 MHz；睡眠唤醒后的限频行为尚未专门验证。

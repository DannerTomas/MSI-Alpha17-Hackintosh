# MSI 雷影17 EFI

2026-10-11，本机 macOS 15.8.1 / OpenCore 1.0.8 RELEASE。Ryzen 9 7945HX、RTX 4060 Laptop、Intel AX210，SMBIOS 为 MacBookPro16,1。

## 正常

- 硬盘 OpenCore 图形菜单，启动 macOS 和 Windows。
- CPU 16 核 32 线程；显卡加速、高斯模糊、内屏 2K 240 Hz、外接显示器（需另装 1401）。
- 键盘、触控板、蓝牙、电池与电源状态；Wi-Fi 使用 itlwm + HeliPort。
- 内置扬声器、有线耳机及拔插切换；耳机需安装附带修复。

## 未正常或受限

- 屏幕亮度调节未修复。
- HiDPI、分辨率切换此前出现闪屏或黑屏，已回退，尚未重新验证。
- 不支持原生 Wi-Fi 菜单。睡眠唤醒、HDMI/DP 音频、耳麦麦克风尚未验证。

## 内容与使用

- `EFI/`：现用完整 EFI，保留本机 SMBIOS 标识及 WindowsDirect 分区绑定，清除旧配置副本和调试日志。
- `HeadphoneFix/`：耳机修复源码和程序。双击 `install.command` 安装，登录后自动运行；`uninstall.command` 停用。仅适配本机 ALC274，需保留 EFI 中的 `alc-verbs`。
- `CPUFrequency/`：4800 MHz 限频源码、自动服务及逐核心频率查看工具。双击 `install.command` 安装，附关闭并恢复原值、重新启用入口；仅适配本机 Ryzen 9 7945HX，需 Apple Command Line Tools。（加这个是因为CPU非常容易积热，在我电脑上实测大于4.8GHz后温度会直线升高，所以准备了这个脚本，如不需要可以不用）

不附带 1401 应用或显卡驱动安装包：[1401 原项目](https://github.com/nullmoth/1401) / [NVIDIA macOS 驱动](https://github.com/nullmoth/nvidia-macos-driver)。

1401驱动经常更新，建议每天都在1401里check一下有没有新版本。

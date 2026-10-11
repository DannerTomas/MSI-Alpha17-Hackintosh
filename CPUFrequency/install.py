"""Install the fixed 4800 MHz helper; --check never opens the hardware interface."""
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent
HELPER = Path('/Library/PrivilegedHelperTools/local.ryzen-4800')
PLIST = Path('/Library/LaunchDaemons/local.ryzen-4800.plist')
JOB = 'system/local.ryzen-4800'
FILES = ('ryzen_4800.py', 'core_watch.py', 'boost-before.json')


def validate():
    for name in FILES + (PLIST.name,):
        path = SOURCE / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('缺少普通文件：' + name)
    for name in ('ryzen_4800.py', 'core_watch.py'):
        compile((SOURCE / name).read_bytes(), name, 'exec')
    before = json.loads((SOURCE / 'boost-before.json').read_text())
    if not (before.get('success') is True and before.get('outputs', [])[0:1] == [5450]
            and before.get('pci_id') == '0x14d81022'):
        raise RuntimeError('5450 MHz 原值记录不符合本机配置。')
    with (SOURCE / PLIST.name).open('rb') as f:
        job = plistlib.load(f)
    expected = {
        'Label': 'local.ryzen-4800',
        'ProgramArguments': ['/usr/bin/python3', '-I', str(HELPER / FILES[0]), 'maintain'],
        'RunAtLoad': True, 'StartInterval': 30, 'ThrottleInterval': 10,
        'ExitTimeOut': 5, 'ProcessType': 'Background',
        'StandardOutPath': '/dev/null', 'StandardErrorPath': '/dev/null',
    }
    if job != expected:
        raise RuntimeError('LaunchDaemon 配置与固定限频服务不一致。')
    def sysctl(key):
        return subprocess.check_output(['/usr/sbin/sysctl', '-n', key], text=True).strip()
    if ('7945HX' not in sysctl('machdep.cpu.brand_string')
            or sysctl('machdep.cpu.family') != '25'
            or sysctl('machdep.cpu.model') != '97'):
        raise RuntimeError('此工具仅用于本机 Ryzen 9 7945HX（Family 0x19 / Model 0x61）。')


def launchctl(*args, check=True):
    return subprocess.run(['/bin/launchctl', *args], check=check, capture_output=True, text=True)


def hardware(action):
    completed = subprocess.run(
        ['/usr/bin/python3', '-I', str(HELPER / FILES[0]), action],
        check=True, capture_output=True, text=True)
    result = json.loads(completed.stdout)
    target = 4800 if action == 'apply' else 5450
    if result.get('success') is not True or result.get('outputs', [])[0:1] != [target]:
        raise RuntimeError('SMU 未确认目标频率：' + completed.stdout)


def secure(path, directory=False):
    info = path.lstat()
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    return info.st_uid == 0 and expected_type(info.st_mode) and not info.st_mode & 0o022


def install():
    if os.geteuid() != 0:
        raise RuntimeError('请通过 install.command 输入管理员密码安装。')
    destinations = [(SOURCE / name, HELPER / name) for name in FILES]
    destinations.append((SOURCE / PLIST.name, PLIST))
    if os.path.lexists(HELPER) or os.path.lexists(PLIST):
        same = (HELPER.is_dir() and not HELPER.is_symlink() and secure(HELPER, directory=True)
                and all(dst.is_file() and secure(dst) and src.read_bytes() == dst.read_bytes()
                        for src, dst in destinations))
        if same:
            print('相同版本已安装，保留当前启停状态。需要开启时运行“重新启用4800MHz限频.command”。')
            return
        raise RuntimeError('目标位置已有不同或不完整的安装，已停止；不会覆盖现有文件。')
    for parent in (HELPER.parent, PLIST.parent):
        parent.mkdir(mode=0o755, exist_ok=True)
        if not secure(parent, directory=True):
            raise RuntimeError('安装目录的类型或权限异常：' + str(parent))
    created = []
    tuning_attempted = False
    HELPER.mkdir(mode=0o755)
    try:
        for src, dst in destinations:
            # Exclusive creation prevents accidental replacement of an existing file.
            with dst.open('xb') as output:
                created.append(dst)
                with src.open('rb') as source:
                    shutil.copyfileobj(source, output)
            os.chown(dst, 0, 0)
            dst.chmod(0o644)
        os.chown(HELPER, 0, 0)
        tuning_attempted = True
        hardware('apply')
        launchctl('enable', JOB)
        launchctl('bootstrap', 'system', str(PLIST))
    except BaseException:
        if tuning_attempted:
            try:
                launchctl('disable', JOB)
                if launchctl('print', JOB, check=False).returncode == 0:
                    launchctl('bootout', JOB)
                hardware('restore')
            except Exception as rollback_error:
                print('自动恢复未完成，保留安装文件；请运行“关闭限频并恢复原值.command”。', file=sys.stderr)
                print(str(rollback_error), file=sys.stderr)
                raise
        for path in reversed(created):
            path.unlink()
        HELPER.rmdir()
        raise
    print('已应用 4800 MHz 目标并安装自动服务，启动时及每 30 秒维护一次。')


def main():
    if sys.argv[1:] not in ([], ['--check']):
        raise SystemExit('用法：install.py [--check]')
    validate()
    if sys.argv[1:] == ['--check']:
        print('文件、Python 语法、服务配置及 CPU 型号检查通过；未修改系统或 CPU 设置。')
    else:
        install()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('安装未完成：' + str(error), file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr or error.stdout or '', file=sys.stderr)
        raise SystemExit(1)

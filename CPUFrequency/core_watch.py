"""Read-only, driver-free per-core display of macOS powermetrics samples."""
import argparse
import datetime
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

FREQ = re.compile(r'^CPU Average frequency.*?\(([0-9.]+) Mhz\)')
CORE = re.compile(r'^Core (\d+) C-state residency:')


def parse_sample(text):
    cores = {}
    core = None
    for line in text.splitlines():
        m = CORE.match(line)
        if m:
            core = int(m.group(1))
            cores[core] = []
        m = FREQ.match(line)
        if m and core is not None:
            cores[core].append(float(m.group(1)))
    return cores


def show(text):
    cores = parse_sample(text)
    if not cores:
        return
    if sys.stdout.isatty():
        print('\033[H\033[2J', end='')
    print('Ryzen 每核心频率 · ' + datetime.datetime.now().strftime('%H:%M:%S'))
    print('数据源：macOS powermetrics；一秒采样平均值，不是瞬时峰值。')
    print('每行一个物理核心，两列分别是该核心的 SMT 线程读数。')
    print('空闲线程读数可能不稳定；请结合负载观察。按 Control+C 退出。\n')
    print('   核心       线程 0 / MHz       线程 1 / MHz')
    print('   ─────────────────────────────────────────')
    for core, values in sorted(cores.items()):
        cols = [f'{v:10.1f}' for v in values[:2]]
        cols += ['       N/A'] * (2 - len(cols))
        print(f'   {core:02d}       {cols[0]}         {cols[1]}')
    print(flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--samples', type=int, default=-1)
    p.add_argument('--from-file')
    args = p.parse_args()
    if args.from_file:
        blocks = Path(args.from_file).read_text().split('*** Sampled system activity')
        show(blocks[-1])
        return
    if os.geteuid() != 0:
        raise SystemExit('请通过“一键查看CPU逐核频率.command”启动；只需在启动时授权一次。')
    command = ['/usr/bin/powermetrics', '--samplers', 'cpu_power', '--hide-cpu-duty-cycle',
               '-b', '1', '-i', '1000', '-n', str(args.samples)]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=None, text=True, start_new_session=True)
    block = []
    try:
        def stop(*_):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGHUP, stop)
        for line in process.stdout:
            if line.startswith('*** Sampled system activity'):
                show(''.join(block))
                block = [line]
            else:
                block.append(line)
        show(''.join(block))
        if process.wait() != 0:
            raise SystemExit('powermetrics 采样失败。')
    except KeyboardInterrupt:
        pass
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()

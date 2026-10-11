"""Narrow Dragon Range SMU helper: cap at 4800 MHz or restore measured 5450.

PCI ABI: Apple IOPCIDiagnosticsClient. SMU opcodes/mailboxes cross-checked
against UXTU RyzenSmu.cs and ZenMaster runner.py/mailbox.py, saved alongside.
No P-state, voltage, power-limit, overclocking-mode, or firmware writes.
"""
import ctypes as c
import datetime
import fcntl
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time


class Params(c.Structure):
    _fields_ = [('options', c.c_uint32), ('space', c.c_uint32),
                ('width', c.c_uint32), ('reserved', c.c_uint32),
                ('value', c.c_uint64), ('address', c.c_uint64)]


class Hardware:
    def __enter__(self):
        if os.geteuid() != 0:
            raise RuntimeError('root is required')
        def sysctl(k):
            return subprocess.check_output(['/usr/sbin/sysctl', '-n', k], text=True).strip()
        self.cpu = sysctl('machdep.cpu.brand_string')
        if ('7945HX' not in self.cpu or sysctl('machdep.cpu.family') != '25'
                or sysctl('machdep.cpu.model') != '97'):
            raise RuntimeError('this helper is restricted to this Ryzen 9 7945HX')
        self.lock = os.open('/var/run/codex-ryzen-4800.lock',
                            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        st = os.fstat(self.lock)
        if st.st_uid != 0 or not stat.S_ISREG(st.st_mode):
            os.close(self.lock)
            raise RuntimeError('unexpected lock file ownership/type')
        try:
            deadline = time.monotonic() + 3
            while True:
                try:
                    fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.02)
        except BaseException:
            os.close(self.lock)
            raise
        self.conn = c.c_uint(0)
        self.selector = None
        try:
            self.io = c.CDLL('/System/Library/Frameworks/IOKit.framework/IOKit')
            libc = c.CDLL('/usr/lib/libSystem.B.dylib')
            self.io.IOServiceMatching.argtypes = [c.c_char_p]
            self.io.IOServiceMatching.restype = c.c_void_p
            self.io.IOServiceGetMatchingService.argtypes = [c.c_uint, c.c_void_p]
            self.io.IOServiceGetMatchingService.restype = c.c_uint
            self.io.IOServiceOpen.argtypes = [c.c_uint, c.c_uint, c.c_uint, c.POINTER(c.c_uint)]
            self.io.IOServiceOpen.restype = c.c_int
            self.io.IOServiceClose.argtypes = [c.c_uint]
            self.io.IOObjectRelease.argtypes = [c.c_uint]
            self.io.IOConnectCallStructMethod.argtypes = [c.c_uint, c.c_uint32,
                c.c_void_p, c.c_size_t, c.c_void_p, c.POINTER(c.c_size_t)]
            self.io.IOConnectCallStructMethod.restype = c.c_int
            task = c.c_uint.in_dll(libc, 'mach_task_self_').value
            service = self.io.IOServiceGetMatchingService(0, self.io.IOServiceMatching(b'IOPCIBridge'))
            if not service:
                raise RuntimeError('IOPCIBridge not found')
            try:
                code = self.io.IOServiceOpen(service, task, 0x99000001, c.byref(self.conn))
            finally:
                self.io.IOObjectRelease(service)
            if code != 0 or not self.conn.value:
                raise RuntimeError('IOPCIBridge open failed: ' + hex(code & 0xffffffff))
            self.pci_id = self.config(0)
            if self.pci_id in (0, 0xffffffff) or self.pci_id & 0xffff != 0x1022:
                raise RuntimeError('PCI 00:00.0 is not an AMD host bridge')
            self.selector = self.config(0xb8)
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, *exc):
        try:
            if self.conn.value:
                try:
                    if self.selector is not None:
                        self.config(0xb8, self.selector)
                finally:
                    self.io.IOServiceClose(self.conn.value)
        finally:
            os.close(self.lock)

    def config(self, reg, value=None):
        if reg not in (0, 0xb8, 0xbc) or (value is not None and reg == 0):
            raise ValueError('PCI operation outside allowlist')
        p = Params(0, 0, 32, 0, value or 0, reg)
        out = Params()
        size = c.c_size_t(c.sizeof(out) if value is None else 0)
        code = self.io.IOConnectCallStructMethod(self.conn, 0 if value is None else 1,
            c.byref(p), c.sizeof(p), c.byref(out) if value is None else None, c.byref(size))
        if code != 0:
            raise RuntimeError('PCI access failed: ' + hex(code & 0xffffffff))
        if value is None and size.value != c.sizeof(out):
            raise RuntimeError('unexpected PCI response length')
        return out.value & 0xffffffff

    def smn_read(self, address):
        self.config(0xb8, address)
        return self.config(0xbc)

    def smn_write(self, address, value):
        self.config(0xb8, address)
        self.config(0xbc, value)

    def ready(self, address):
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            value = self.smn_read(address)
            if value:
                return value
            time.sleep(0.001)
        raise RuntimeError('SMU response timeout; no retry or alternate opcode attempted')

    def command(self, operation):
        if operation == 'query':
            msg, rsp, args, opcode, value = 0x3b10524, 0x3b10570, 0x3b10a40, 0x6e, 0
        elif operation in ('apply', 'restore'):
            # 5450 was read from this CPU before any tuning (boost-before.json).
            target = 4800 if operation == 'apply' else 5450
            msg, rsp, args, opcode, value = 0x3b10530, 0x3b1057c, 0x3b109c4, 0x2b, target
        else:
            raise ValueError('allowed operations: query, apply, restore')
        prior = self.ready(rsp)
        if prior not in (1, 0xff, 0xfe, 0xfd, 0xfc):
            raise RuntimeError('unrecognized SMU status: ' + hex(prior))
        self.smn_write(rsp, 0)
        for i in range(6):
            self.smn_write(args + i * 4, value if i == 0 else 0)
        self.smn_write(msg, opcode)
        response = self.ready(rsp)
        outputs = [self.smn_read(args + i * 4) for i in range(6)]
        return {'operation': operation, 'opcode': hex(opcode), 'argument': value,
                'response': hex(response), 'success': response == 1, 'outputs': outputs}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('probe', 'query', 'apply', 'restore', 'maintain'):
        raise SystemExit('Usage: ryzen_4800.py probe|query|apply|restore|maintain')
    action = sys.argv[1]
    if action == 'maintain':
        # Finish the bounded mailbox transaction if launchd unloads this job.
        signal.signal(signal.SIGTERM, lambda *_: None)
    result = {'time': datetime.datetime.now().astimezone().isoformat()}
    try:
        with Hardware() as hw:
            result.update(cpu=hw.cpu, pci_id=hex(hw.pci_id))
            if action != 'probe':
                result.update(hw.command('apply' if action == 'maintain' else action))
    except Exception as e:
        result.update(success=False, error=str(e))
    if action == 'maintain' and os.geteuid() == 0:
        # A bounded status file, rather than an indefinitely growing success log.
        fd, tmp = tempfile.mkstemp(prefix='.ryzen-4800-', dir='/var/run')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(result, f, indent=2)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o644)
            os.replace(tmp, '/var/run/ryzen-4800-status.json')
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    else:
        print(json.dumps(result, indent=2))
    if result.get('success') is False:
        raise SystemExit(2)


if __name__ == '__main__':
    main()

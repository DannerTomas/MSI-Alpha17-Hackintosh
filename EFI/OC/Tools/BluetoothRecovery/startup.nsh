@echo -off
echo Restore the working OpenCore configuration with Bluetooth disabled.
if not exist %homefilesystem%\EFI\OC\Tools\BluetoothRecovery\INTERNAL-B17EF675-4F43-4195-841F-7AE8844961A8.tag then
  goto wrong_disk
endif
set -v BTREC_DIR %homefilesystem%\EFI\OC\Tools\BluetoothRecovery
if not exist %BTREC_DIR%\config-no-bluetooth.plist then
  goto missing
endif
if not exist %BTREC_DIR%\config-test.plist then
  goto missing
endif
if not exist %homefilesystem%\EFI\OC\config.plist then
  goto missing
endif
comp %homefilesystem%\EFI\OC\config.plist %BTREC_DIR%\config-no-bluetooth.plist > %BTREC_DIR%\compare-stable.txt
if %lasterror% == 0 then
  goto done
endif
comp %homefilesystem%\EFI\OC\config.plist %BTREC_DIR%\config-test.plist > %BTREC_DIR%\compare-test.txt
if not %lasterror% == 0 then
  goto changed
endif
echo Press any key to restore the working configuration. Ctrl-C cancels.
pause
cp -q %homefilesystem%\EFI\OC\config.plist %BTREC_DIR%\config-before-restore.plist
if not %lasterror% == 0 then
  goto failed
endif
comp %homefilesystem%\EFI\OC\config.plist %BTREC_DIR%\config-before-restore.plist > %BTREC_DIR%\compare-backup.txt
if not %lasterror% == 0 then
  goto failed
endif
cp -q %BTREC_DIR%\config-no-bluetooth.plist %homefilesystem%\EFI\OC\config.plist
if not %lasterror% == 0 then
  goto restore_failed
endif
comp %homefilesystem%\EFI\OC\config.plist %BTREC_DIR%\config-no-bluetooth.plist > %BTREC_DIR%\compare-restored.txt
if not %lasterror% == 0 then
  goto restore_failed
endif
:done
echo DONE - the working configuration is restored. Bluetooth is disabled.
echo Press any key to SHUT DOWN, then power on again.
pause
reset -s
echo Firmware shutdown returned. Please power off manually.
goto stopped
:wrong_disk
echo STOP - the internal recovery marker was not found.
goto stopped
:missing
echo STOP - a required recovery file is missing. Use the working USB.
goto stopped
:changed
echo STOP - configuration has changed since this test. No restore was performed.
goto stopped
:restore_failed
echo STOP - restore failed; attempting to put back the saved test configuration.
cp -q %BTREC_DIR%\config-before-restore.plist %homefilesystem%\EFI\OC\config.plist
echo Use the working USB to boot and inspect the internal EFI.
goto stopped
:failed
echo STOP - backup or verification failed. No restore was performed.
:stopped
echo Press any key to return to the OpenCore menu.
pause
exit

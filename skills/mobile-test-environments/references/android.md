# Android

## Inventory and selection

Use the bundled inventory for a compact first look. For detail, resolve `adb`
and `emulator` from PATH, `ANDROID_HOME`, or the legacy `ANDROID_SDK_ROOT`.
Common SDK roots are `~/Library/Android/sdk` on macOS and `~/Android/Sdk` on Linux.

- `emulator -list-avds` lists installed AVD configurations, not running phones.
- `adb devices -l` lists connected devices and can start the ADB daemon. The
  inventory helper queries the host service at `127.0.0.1` directly, using
  `ANDROID_ADB_SERVER_PORT` or its default port. It skips the query when
  `ADB_SERVER_SOCKET` is set. Inspect other endpoint settings such as
  `ANDROID_ADB_SERVER_ADDRESS` before using the ADB CLI.
- Preserve `offline` and `unauthorized` states. They are not ready test devices. Trust prompts on a physical phone belong to its user.

Choose the exact AVD and serial. Reuse the project-approved booted emulator when available. When starting an AVD, select a free even console port with the next port free for ADB. Record the process/session and eventual serial. Run `-avd "$AVD_NAME" -port "$EMULATOR_PORT"` with the discovered emulator executable in a managed tool session. Add `-no-window` only for a hidden screen.

Poll `adb -s "$DEVICE_SERIAL" shell getprop sys.boot_completed` with a bounded deadline and check the device remains connected. A process starting is not a completed boot. Preserve existing user data; `-wipe-data` and snapshot reload are not troubleshooting defaults. For an explicitly disposable run, `-read-only -no-snapshot-save` can avoid persisting changes; record that choice and its limitations.

## See the screen

For an installed scrcpy, `scrcpy --serial "$DEVICE_SERIAL" --no-control` mirrors the chosen screen without injecting user input into an active test. Omit `--no-control` only when interactive control is intended. Reuse an existing emulator window or Android Studio viewer when available. Appium Inspector is optional; observing an existing test uses **Attach to Session**, not a competing automation session.

Do not reinstall Maestro to obtain a screen. If no viewer is installed, capture a screenshot with the existing Appium client or `adb -s "$DEVICE_SERIAL" exec-out screencap -p > "$SCREENSHOT_PATH"`. Save it to a task artifact path and open the image.

## Keyboard and instrumentation failures

For keyboard coverage, tap the editable control and establish that the normal software keyboard is visible. Appium's `mobile: isKeyboardShown` plus an actual screenshot/visible viewport provide evidence; entering text through a hidden/custom IME does not. Re-query element bounds after the keyboard changes the viewport. Verify the focused field and footer/close actions remain reachable and the draft survives dismissal or mode changes required by the app.

If an input command changes the selected IME, inspect the resulting state before another attempt. Restore only a setting changed by this task, on its exact device. Do not change global keyboard or personal-phone settings to make a test pass. If hardware-keyboard configuration suppresses the software keyboard, record it and use an authorized test-device configuration.

`UiAutomation not connected` can indicate overlapping instrumentation, for example Appium and Maestro targeting one emulator. Inspect the exact device's instrumentation/processes and their owner. Stop only a task-owned competing driver, then make a bounded retry. Unknown ownership is a coordination boundary, not permission to force-stop packages or restart the shared ADB server.

## Stop

For an emulator started by this task, `adb -s "$DEVICE_SERIAL" emu kill` targets one instance. Verify its identity first. Leave pre-existing emulators, the shared ADB server and unrelated device connections intact.

Sources: [Android emulator CLI](https://developer.android.com/studio/run/emulator-commandline), [ADB](https://developer.android.com/tools/adb), [read-only host protocol](https://android.googlesource.com/platform/packages/modules/adb/+/HEAD/docs/dev/services.md), [scrcpy controls](https://github.com/Genymobile/scrcpy/blob/master/app/scrcpy.1).

# iOS and virtual iPhones

## Resolve the installed tools

Use `xcode-select -p` and the current process's `DEVELOPER_DIR`, when set, to identify the intended Xcode. Do not switch the global developer directory to solve a task-local problem. Inspect CLI help for the installed toolchain when commands differ.

`xcrun simctl list devices available --json` identifies available devices and
their states. An empty successful list calls for a separate check of installed
runtimes with `xcrun simctl list runtimes --json`. Report command errors such
as incomplete first-launch setup, license prompts or denied CoreSimulator
access. Check device boot state and viewer visibility separately.

For viewer discovery, inspect the selected Xcode bundle:

- Xcode 27 introduces **Device Hub**. Its app may be under `Contents/Applications/DeviceHub.app`.
- Earlier Xcode installations commonly bundle `Contents/Developer/Applications/Simulator.app`.
- Probe actual files and the current Apple documentation; do not infer that iOS support is absent from one missing historic path or a failed Spotlight search.

The bundled helper checks both layouts. With Device Hub, choose **Simulators** in the sidebar filter for virtual phones; **Physical Devices** is a separate set. A missing GUI and a missing runtime are different conditions.

## Start, view and use a virtual phone

Select an explicit available UDID. If it is already booted, reuse it and retain its prior state. Otherwise use `xcrun simctl boot "$IOS_UDID"` and poll the selected device state with a deadline. `simctl bootstatus "$IOS_UDID" -b` is an alternative only with a bounded process timeout. Never boot or shut down every simulator.

Open the discovered Device Hub/Simulator app with `open "$VIEWER_APP"` only when a visible screen is requested. In Device Hub, select the device and click **Start** if needed; the selected running device's screen appears in the canvas. Xcode's editor need not stay open. A booted CLI simulator does not guarantee an already-open screen window.

Use `xcrun simctl openurl "$IOS_UDID" "$TEST_URL"` for the chosen local test route and `xcrun simctl io "$IOS_UDID" screenshot "$SCREENSHOT_PATH"` for an image. Keep app operations scoped to that UDID. Open the saved image to verify the result instead of treating command success as visual acceptance.

Create a new simulator only when the user/task actually requires one: obtain valid device-type/runtime identifiers from `simctl list --json`, choose the requested combination, and record the returned UDID. Missing runtime downloads or a new Xcode installation are setup changes, not an implicit repair step. Offer the required platform/version without downloading every runtime.

## Physical iPhone

For testing, read [Appium](appium.md) and follow the selected XCUITest driver's real-device preparation. Device pairing, trust, Developer Mode, signing identities and provisioning need user/owner involvement; never borrow credentials or enable broad permissions automatically.

For viewing only, Device Hub can show/control supported paired physical devices. Built-in iPhone Mirroring is another option when its account/OS/region requirements are met. QuickTime Player can show or record a connected phone over USB using **File → New Movie Recording → Camera → iPhone**; it is not a general remote-control or automated-test facility. Do not claim a phone screen is connected until observed.

## Stop

Use `xcrun simctl shutdown "$IOS_UDID"` only for an identified device booted for this task and approved for teardown. Delete/erase operations need explicit scope. Closing a viewer window is not equivalent to shutting down a simulator. Preserve pre-existing devices and the installed runtimes.

Sources: [Device Hub](https://developer.apple.com/documentation/xcode/managing-your-simulated-and-physical-devices-in-device-hub), [independent launch](https://developer.apple.com/videos/play/wwdc2026/260/), [Xcode components](https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components), [iPhone Mirroring](https://support.apple.com/en-us/120421), [QuickTime](https://support.apple.com/guide/quicktime-player/record-a-movie-qtp356b55534/mac).

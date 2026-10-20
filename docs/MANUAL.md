# User manual — Pupovina 1.4.0

*by Dmitrij Musella*

## What it does

Pupovina lets an Android phone **use the computer's internet connection over the USB
cable**. It is the opposite of a normal hotspot, which is why it is called *reverse
tethering*. No root is needed, neither on the phone nor on the computer.

The program is a graphical interface for **gnirehtet** by Genymobile: it does for you
everything you would otherwise type in a terminal, and it also shows the speed and
traffic of each phone.

It works on **Windows** and **Linux**, in **Italian, English and Russian**. Gnirehtet
carries TCP and UDP traffic over IPv4 (IPv6 is not supported).

## Installation

**Ready-made build (recommended)**: from the project's *Releases* page on GitHub download
`Pupovina.exe` for Windows or `Pupovina-x86_64.AppImage` for Linux. Python is not
required. On Linux make the AppImage executable (`chmod +x`) and run it.

**From source**: install Python 3.9 or later and PyQt6 (`pip install PyQt6`), then run
`python pupovina.py`.

The phone needs Android 5.0 or later, **USB debugging** enabled and a USB cable that
carries data. To enable USB debugging: *Settings → About phone*, tap **Build number**
seven times to unlock *Developer options*, then in *Developer options* turn on
**USB debugging**.

## First start

1. In the **Tools** panel press **Download gnirehtet**. The program downloads the official
   Rust version 2.5.1, verifies its SHA-256 fingerprint and installs it.
2. If adb is not already on the computer, press **Download adb (platform-tools)**.
   It comes from the official Android website.
3. Connect the phone. The prompt *Allow USB debugging?* appears on its screen: accept it
   (preferably with *Always allow from this computer*).
4. Select the phone in the list and press **Start tethering**.
5. The first time, the gnirehtet app is installed on the phone, which asks you to
   **allow a VPN connection**: confirm. When it is active, a key icon appears in the
   phone's status bar.

The downloaded tools stay on the computer, in the folder:

`Windows: %LOCALAPPDATA%\GnirehtetGUI\tools — Linux: ~/.local/share/GnirehtetGUI/tools`

On later starts they are found automatically and are not downloaded again.

## The main window

### Tools
Shows where **gnirehtet** and **adb** are (✔ found, ✘ missing), the adb version and the
state of the **relay**, the small server that forwards the phone's traffic to the
internet. The relay starts automatically with the first tethering and stops when you quit.

- **Update adb** checks Google's website for a newer adb and, if there is one, downloads
  and installs it. Tethering must be stopped on all phones before updating. If adb was
  installed system-wide, from then on the program uses its own updated copy.
- **Open tools folder** opens the folder where gnirehtet and adb are stored.
- **Check processes** looks for gnirehtet processes left open by earlier sessions (for
  example after a crash) and other copies of the program, lists them with PID and command,
  and closes the ones you select. The relay currently in use is never listed. The same check
  runs by itself at startup and reports any findings in the console. The program also cannot
  be opened twice: a second launch brings the existing window to the front.

### Connected devices
List of the phones detected by adb, refreshed every 2 seconds.

| Column | Meaning |
|---|---|
| Device | Phone model |
| Serial | Identifier used by adb |
| ADB state | *Ready*, *Unauthorized*, *Offline*, *Missing USB permissions* |
| Tethering | *Off*, operation in progress, *Active* or *Error* with the reason |
| Speed | The phone's current ↓ download and ↑ upload |
| Traffic | Data downloaded (↓) and sent (↑) since tethering started |

Speed and traffic are read directly from the phone, on gnirehtet's VPN interface: if the
numbers move, **the network really works**. If traffic is still zero after about twenty
seconds, the Tethering column shows *no traffic yet*; if the VPN is not active at all it
shows *VPN not active on the phone?*, usually because the VPN request was not confirmed.

Buttons:

- **Start tethering**: checks that the app is installed on the phone (installs it if
  missing), starts the relay if needed and enables the connection.
- **Stop**: turns off the connection on the selected phone.
- **Reset tunnel**: rebuilds the link between phone and computer without stopping
  everything. Useful if the network hangs after unplugging and replugging the cable.
- **Double-click** a row: starts or stops tethering on that phone.

You can connect **several phones at once**: each one is managed from its own row.

### Autorun
With the **Autorun** box ticked, tethering starts by itself on every phone you plug in.
The choice is remembered.

Regardless of autorun, if you unplug a phone while it is active, the program re-enables
it when you plug it back in.

### Console
Log of everything that happens: executed commands (blue), relay messages (grey),
successful operations (green), warnings (orange) and errors (red). **Copy all** copies
the log to the clipboard, useful when asking for help; **Clear** empties it.

## Icon and notifications

Closing the window **does not quit** the program: it stays in the notification area,
next to the clock, and tethering keeps working.

- **Grey** icon: no phone connected.
- **Green** icon: at least one phone is using the computer's network.
- **Red** icon: there is an error.

Hovering over the icon shows how many phones are tethering and the total speed. A click
shows or hides the window. Right-click for *Show window*, *Autorun*, *Stop all* and
**Quit**. To really close the program use **Quit**, from the icon or the *File* menu.

The program shows a **notification** when a phone is connected or disconnected, when
tethering becomes active and when an error occurs. Notifications can be turned off in
Settings.

## Settings

From *File → Settings* or the **Settings…** button:

- **gnirehtet / adb path**: leave empty for automatic search, or point to a specific
  executable.
- **Relay port**: default 31416. Change it only if it is already in use.
- **DNS servers**: for example `1.1.1.1,8.8.8.8`. Empty means the defaults.
- **Language**: Italian, English or Russian (also from the *Language* menu). On first start
  the program uses the system language. Changing it requires a restart, which the program
  offers to do right away.
- **Show notifications**: turns notifications on or off.
- **Stop tethering on the phones when quitting**: recommended, otherwise the VPN stays on
  on the phone without carrying traffic.
- **Start hidden in the notification area**: the program starts without showing the window.

Port and DNS changes apply from the next tethering start.

## Command line

```
python pupovina.py            normal start
python pupovina.py --hidden   start directly in the notification area
```

The `--hidden` option also works with the executable and the AppImage.

## Troubleshooting

**The phone does not appear in the list**
Check that USB debugging is enabled and that the cable carries data. On some phones you
need to pick the *File transfer* USB mode.

**State «Unauthorized»**
Unlock the phone and accept the USB debugging prompt. If it does not appear, use
*Revoke USB debugging authorizations* in *Developer options* and replug the cable.

**State «Missing USB permissions» (Linux only)**
The Android udev rules are missing: install `android-sdk-platform-tools-common`
(Debian/Ubuntu) or `android-udev-rules` (Arch, Fedora), then replug the cable.

**«Relay not started» or «port 31416 in use»**
Another program is already using the port. If it is a leftover gnirehtet, the program
closes it automatically when starting; you can also use **Check processes**. If it is a
different program, close it or change the port in Settings.

**Tethering «Active» but the phone cannot browse**
Look at the Speed and Traffic columns. If *VPN not active on the phone?* appears, unlock
the phone and confirm the VPN request. If the VPN is active but traffic stays at zero,
check that the computer is online, then try **Reset tunnel**, or **Stop** and **Start**
again.

**Windows Firewall**
When the relay first starts, Windows may ask to allow network access for gnirehtet:
allow it at least for private networks.

**Windows SmartScreen**
The executable is not digitally signed, so on first launch Windows may show *Windows
protected your PC*: choose *More info → Run anyway*.

## Privacy

The program collects and sends no data. It goes online only when you press **Download**
or **Update adb**, to fetch gnirehtet from GitHub and adb from Google's website.
Settings stay on your computer.

## Credits

Pupovina — © 2026 Dmitrij Musella.

Based on [gnirehtet](https://github.com/Genymobile/gnirehtet) by Genymobile, released
under the Apache 2.0 license. adb is part of Google's Android SDK Platform Tools.

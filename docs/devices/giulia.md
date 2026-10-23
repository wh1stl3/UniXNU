# OnePlus Ace 5 (giulia)

giulia is the OnePlus Ace 5 (PKG110) with the SM8650 SoC. The port below is an independent community project. The UniXNU organization does not maintain it. The kernel is a Darwin 22.6 / iOS 16 build.

| Repository | Maintainer | State |
| --- | --- | --- |
| [UniXNU-giulia](https://github.com/jasper2863/UniXNU-giulia) | [jasper2863](https://github.com/jasper2863) | GUI progress bar reached; installation service blocked |
| [UniXNU-OnePlus-Ace5](https://github.com/tycykp/UniXNU-OnePlus-Ace5) | [tycykp](https://github.com/tycykp) | Hello and Setup reached with full display and touch; GPU and Wi-Fi pending |

## State

| Area | State |
| --- | --- |
| UEFI handoff and XNU memory initialization | works |
| Platform drivers, CPU0 and SGI1 | works |
| Native UFS read | works |
| USB CDC debug serial | works |
| HFSX root volume | read and write mount works |
| `launchd` and system services | start |
| GUI kernel | Apple logo and progress bar; about 77,000 frame submissions logged; no SpringBoard or backboardd crash observed |
| Usable UI | not reached; the installation service is blocked |
| Touch | controller identity and packets verified; physical touch not usable |
| Baseband, audio, GPU and DRM | not implemented |

The repository keeps the full boot logs, host checks and image hashes. The current blocker is the system app installation and migration path.

## tycykp repository

`UniXNU-OnePlus-Ace5` records a separate iOS 16 / Darwin 22 bring-up. Its 2026-10-23 device test reached Hello and Setup with full 1264x2780 panel coverage and aligned touch. UEFI handoff, XNU startup on one core, native UFS reads, USB CDC serial, HFSX root mount and `launchd` startup are verified. Wi-Fi PCIe, BHI/BHIE, AMSS and QMI resource requests are verified, but the latest run stops at QMP open before firmware-ready. GPU has a preparation service only. Audio has experimental runtime cores with no device playback. Cellular and DRM are unverified.

## Maintenance

The maintainer owns the repository and its release decisions. UniXNU documentation lists the port and its state; it does not take over maintenance.

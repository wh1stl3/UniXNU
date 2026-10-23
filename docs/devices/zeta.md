# Microsoft Surface Duo 2 (zeta)

zeta is the Microsoft Surface Duo 2 with the SM8350 SoC. The port below is an independent community project. The UniXNU organization does not maintain it. The target identity is iPhone18,2 on iOS 26.5.2.

| Repository | Maintainer | State |
| --- | --- | --- |
| [UniXNU-zeta](https://github.com/none24smu/UniXNU-zeta) | [none24smu](https://github.com/none24smu) | Kernel and root bring-up reach the launchd exec; arm64e launchd stops |

## State

| Step | State |
| --- | --- |
| UEFI firmware | boots on the phone with `fastboot boot`; UniXNU menu on the panel, volume and power keys work, the boot image ramdisk mounts as the payload volume |
| Device repository | this repository |
| IPSW identity | iPhone18,2 26.5.2 23F84 |
| ADT | zeta hardware values with the iPhone18,2 identity from the IPSW device tree |
| Payload and boot image | xnu-12377.121.6 (iOS 26.5) from the UniXNU `ios26` branch; DarwinBoot loads the kernel, ADT and boot arguments; paired reset probes reached `arm_init` and BSD pthread initialization |
| Root and userland | native UFS reads, both owner policy tables, APFS, the OS root mount, owner root authorization, early AMFI registration and decmpfs zlib reads work; PID 1 reaches the launchd exec, which fails with `EBADARCH` because launchd is arm64e and the CPU has no pointer authentication |

The firmware half is [uefi-zeta](https://github.com/none24smu/uefi-zeta), a Mu-Silicium tree with `Platforms/Microsoft/zetaPkg`.

## Maintenance

The maintainer owns the repository and its release decisions. UniXNU documentation lists the port and its state; it does not take over maintenance.

# OnePlus Ace 5 Pro (hummer)

hummer is the OnePlus Ace 5 Pro (PKR110) with the SM8750 SoC. The port below is an independent community project. The UniXNU organization does not maintain it.

| Repository | Maintainer | State |
| --- | --- | --- |
| [UniXNU-hummer](https://github.com/2426120557/UniXNU-hummer) | [2426120557](https://github.com/2426120557) | UEFI works; XNU SMP and bootstrap checkpoints on the panel |

## State

| Area | State |
| --- | --- |
| UEFI firmware and menu | works on hardware; GOP display and key input |
| XNU kernel | SMP works; secondaries reach the scheduler; kernel bootstrap checkpoints draw on the panel; root not reached |
| GPU (Adreno 830) | not started |
| Persistent Data | not started |

The v51 kernel pairs the boot-progress checkpoints with `kboot` lines on the panel, so the early bootstrap is visible without the boot-progress diagnostic page. The board file still marks `[kernel]`, `[ipsw]` and `[payload]` as scaffolding. The README names the GPU as the main blocker.

## Maintenance

The maintainer owns the repository and its release decisions. UniXNU documentation lists the port and its state; it does not take over maintenance.

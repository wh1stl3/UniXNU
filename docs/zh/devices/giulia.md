# 一加 Ace 5（giulia）

giulia 是搭载 SM8650 的一加 Ace 5（PKG110）。下面的移植是独立的社区项目，UniXNU 组织不维护它。内核为 Darwin 22.6 / iOS 16 构建。

| 仓库 | 维护者 | 状态 |
| --- | --- | --- |
| [UniXNU-giulia](https://github.com/jasper2863/UniXNU-giulia) | [jasper2863](https://github.com/jasper2863) | 已到 GUI 进度条，安装服务受阻 |
| [UniXNU-OnePlus-Ace5](https://github.com/tycykp/UniXNU-OnePlus-Ace5) | [tycykp](https://github.com/tycykp) | 已到 Hello 和 Setup，显示完整、触控可用；GPU 和 Wi-Fi 待完成 |

## 状态

| 区域 | 状态 |
| --- | --- |
| UEFI 交接和 XNU 内存初始化 | 工作 |
| 平台驱动、CPU0 和 SGI1 | 工作 |
| 原生 UFS 读取 | 工作 |
| USB CDC 调试串口 | 工作 |
| HFSX 根卷 | 读写挂载工作 |
| `launchd` 和系统服务 | 启动 |
| GUI 内核 | 苹果标志和进度条，记录约 77,000 次画面提交，未观察到 SpringBoard 或 backboardd 崩溃 |
| 可操作界面 | 未到达，安装服务受阻 |
| 触控 | 控制器身份和报文已验证，物理触控不可用 |
| 基带、音频、GPU 和 DRM | 未实现 |

仓库保留了完整启动日志、主机检查和镜像哈希。当前阻塞点是系统应用安装和迁移路径。

## tycykp 仓库

`UniXNU-OnePlus-Ace5` 记录了另一条 iOS 16 / Darwin 22 bring-up。2026-10-23 的真机测试到达 Hello 和 Setup，1264x2780 面板完整显示，触控对齐可用。已验证 UEFI 交接、单核 XNU 启动、原生 UFS 读取、USB CDC 串口、HFSX 根卷挂载和 `launchd` 启动。Wi-Fi 的 PCIe、BHI/BHIE、AMSS 和 QMI 资源请求已验证，但最新运行停在 QMP open，尚未到 firmware-ready。GPU 只有准备服务。音频有实验性运行时组件，未在真机播放。蜂窝和 DRM 未验证。

## 维护

维护者拥有仓库和发布决定。UniXNU 文档记录移植及其状态，不接管维护。

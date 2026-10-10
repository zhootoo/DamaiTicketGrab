# Damai Android Clicker

一个面向 **大麦（Damai）抢票** 场景的 Android 端高频自动点击脚本。基于 [`uiautomator2`](https://github.com/openatx/uiautomator2) 通过 ADB 控制安卓设备，在指定开抢时间点以毫秒级精度执行两阶段点击策略，并提供运行中的实时暂停 / 继续 / 退出控制。

> 本项目仅供学习 Python 自动化、ADB 与时间精度控制使用，请遵守平台服务条款与相关法律法规。

---

## 功能特性

- **精确时间触发**：使用 Windows 高精度计时器（`timeBeginPeriod(1)`）+ 忙等待，把点击启动误差压到毫秒级。
- **提前量补偿**：通过 `lead_seconds` 抵消 `uiautomator2` 的通信延迟，使实际点击时刻对齐目标时间 `T1`。
- **两阶段点击策略**：
  - **Phase 1（时长 `T2`）**：只点击坐标 `P1`（例如「立即购买」按钮）。
  - **Phase 2（无限循环）**：在 `P1` 与 `P2` 之间轮流点击，用于处理开抢后弹出的确认按钮。
- **运行中热控制**：无需重启脚本，键盘实时控制：
  - `v` 暂停（同时自动补偿暂停时长，不损失有效点击时间）
  - `c` 继续
  - `q` 退出
- **配置与代码分离**：所有时间与坐标参数集中在 `config.toml`，无需改代码。
- **实时统计**：每阶段打印点击次数与每秒点击频率（次/秒）。

---

## 工作原理

```
时间轴
  T1 - lead_seconds             T1                    T1 + T2
        │                        │                       │
        │◄── Phase 1（只点 P1）──►│◄──── Phase 2 ────────►│
   精确等待并开始高频点击      每分钟/每秒级轮流点击 P1、P2
```

1. 从 `config.toml` 读取目标时间 `T1`、Phase 1 时长 `T2`、提前量 `lead_seconds` 与坐标 `P1`、`P2`。
2. 提前连接设备（避免占用点击时间）。
3. 倒计时显示剩余时间，最后阶段调用 `wait_until` 忙等待精确到目标时刻。
4. 进入 Phase 1：在 `T2` 秒内以最高频率点击 `P1`。
5. 进入 Phase 2：无限循环轮流点击 `P1` / `P2`，直到按 `q` 或 `Ctrl+C`。
6. 按下 `v` 暂停时，`click_phase` 会自动把暂停耗时补回到 deadline，保证总点击时长不变。

---

## 环境要求

- **Windows**（依赖 `msvcrt`、`ctypes.windll.winmm` 等高精度计时 API）
- **Python >= 3.11**（使用标准库 `tomllib`）
- **ADB** 已安装并加入 `PATH`
- 一台已开启 **USB 调试** 的 Android 设备（USB 连接或 `adb connect` 无线连接）
- 推荐使用 [`uv`](https://docs.astral.sh/uv/) 管理依赖

---

## 安装

```bash
# 克隆仓库
git clone https://github.com/zhootoo/DamaiTicketGrab.git
cd DamaiTicketGrab

# 使用 uv 安装依赖（推荐）
uv sync

# 或者使用 pip
pip install uiautomator2
```

确认设备连接正常：

```bash
adb devices
```

---

## 配置说明（config.toml）

```toml
[timing]
# 目标点击开始时间，格式: "YYYY-MM-DD HH:MM:SS"
T1 = "2026-07-09 20:00:00"

# Phase 1 持续时长（秒）：只点击 P1 的时间
T2 = 4

# 提前量（秒）：在 T1 前多少秒开始点击，用于补偿 uiautomator2 的延迟
lead_seconds = 0.85

[coordinates]
# P1 坐标 [x, y]，Phase 1 期间只点 P1
P1 = [845, 2299]

# P2 坐标 [x, y]，Phase 2 期间与 P1 轮流点击
P2 = [541, 1506]
```

| 参数 | 含义 | 说明 |
| --- | --- | --- |
| `T1` | 目标开抢时刻 | 建议比平台实际开售时间提前，人眼看到「已开售」时点击已晚 |
| `T2` | Phase 1 时长（秒） | P1 单独点击的持续时间 |
| `lead_seconds` | 提前量（秒） | 用于补偿 ADB / uiautomator2 通信延迟，需按设备实测微调 |
| `P1` | 主按钮坐标 | 例如「立即购买」 |
| `P2` | 次按钮坐标 | 例如开抢后弹出的确认按钮 |

> 坐标获取：Android 开发者选项 → 「指针位置」，或使用 `uiautomator2` / `adb shell getevent` 查看屏幕坐标。

---

## 使用方法

**方式一：双击 `run.bat`**（自动 `cd` 到项目目录并运行）

**方式二：命令行运行**

```bash
uv run python main.py
```

运行后：

1. 脚本自动连接设备并打印设备名。
2. 屏幕显示倒计时，等待 `T1 - lead_seconds`。
3. 进入 Phase 1 / Phase 2 后开始高频点击。

### 运行中控制键

| 按键 | 功能 |
| --- | --- |
| `v` | 暂停（自动补偿暂停时长） |
| `c` | 继续运行 |
| `q` | 退出程序 |
| `Ctrl+C` | 强制中断 |

---

## 项目结构

```
DamaiTicketGrab/
├── main.py          # 主程序：计时、点击策略、键盘控制
├── config.toml      # 时间与坐标配置
├── pyproject.toml   # 项目元数据与依赖
├── run.bat          # Windows 一键运行脚本
├── uv.lock          # uv 依赖锁文件
└── README.md
```

---

## 调优建议

- **`lead_seconds` 是关键参数**：`uiautomator2` 单次点击存在固定延迟，需实测后微调（建议先设为 0，观察点击与目标时刻的偏差再补偿）。
- **坐标要提前校准**：不同分辨率、不同 App 版本的按钮位置不同，建议开抢前先测试 `P1` / `P2` 是否命中。
- **保持设备唤醒**：开抢前保持屏幕常亮、关闭省电模式，避免设备休眠导致连接断开。
- **建议使用 USB 直连**：无线 ADB 延迟更高，可能影响精度。

---

## 免责声明

本项目仅用于学习 Python 自动化、ADB 操作与高精度时间控制等技术，**请勿用于违反目标平台服务条款的行为**。使用者需自行承担一切后果，作者不对任何滥用行为或由此产生的损失承担责任。

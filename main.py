import ctypes
import msvcrt
import sys
import threading
import time
import tomllib
from datetime import datetime

import uiautomator2 as u2


# ── 全局控制状态 ──────────────────────────────────────────────────────────────
_running = threading.Event()
_running.set()   # set = 运行中，clear = 已暂停
_quit = threading.Event()


def _keyboard_listener() -> None:
    """后台线程：监听 p/c/q 按键。"""
    while not _quit.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getwch().lower()
            if key == "v":
                if _running.is_set():
                    _running.clear()
                    print("\n[已暂停]  输入 c 继续，q 退出")
            elif key == "c":
                if not _running.is_set():
                    _running.set()
                    print("\n[继续运行]")
            elif key == "q":
                _quit.set()
                _running.set()   # 解除任何因暂停而阻塞的等待
                print("\n[正在退出...]")
        time.sleep(0.05)


# ── Windows 高精度计时器 ─────────────────────────────────────────────────────
def _set_timer_resolution():
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except AttributeError:
        pass


def _restore_timer_resolution():
    try:
        ctypes.windll.winmm.timeEndPeriod(1)
    except AttributeError:
        pass


# ── 精确等待 ─────────────────────────────────────────────────────────────────
def wait_until(target: float, busy_wait_threshold: float = 0.015) -> None:
    gap = target - time.time()
    if gap > busy_wait_threshold:
        time.sleep(gap - busy_wait_threshold)
    while time.time() < target:
        pass


# ── 点击循环 ─────────────────────────────────────────────────────────────────
def click_phase(d: u2.Device, coords: list[tuple[int, int]], duration: float) -> int:
    """
    在 duration 秒内对 coords 中的坐标循环高频点击。
    暂停期间自动延长 deadline，保证实际点击时长不变。
    返回实际点击总次数。
    """
    end = time.perf_counter() + duration
    count = 0
    idx = 0
    n = len(coords)
    while time.perf_counter() < end and not _quit.is_set():
        if not _running.is_set():
            pause_start = time.perf_counter()
            _running.wait()
            end += time.perf_counter() - pause_start   # 补偿暂停时长
            if _quit.is_set():
                break
        x, y = coords[idx % n]
        d.click(x, y)
        count += 1
        idx += 1
    return count


# ── 无限点击（Ctrl+C 或 q 退出）─────────────────────────────────────────────
def click_infinite(d: u2.Device, coords: list[tuple[int, int]]) -> int:
    count = 0
    idx = 0
    n = len(coords)
    try:
        while not _quit.is_set():
            if not _running.is_set():
                _running.wait()
                if _quit.is_set():
                    break
            x, y = coords[idx % n]
            d.click(x, y)
            count += 1
            idx += 1
    except KeyboardInterrupt:
        pass
    return count


# ── 倒计时显示 ────────────────────────────────────────────────────────────────
def countdown(target: float) -> None:
    while not _quit.is_set():
        remaining = target - time.time()
        if remaining <= 0.5:
            break
        print(f"\r  等待开始点击 ... {remaining:6.1f}s 后  [p=暂停 q=退出]", end="", flush=True)
        time.sleep(0.1)
    print()


# ── 主流程 ────────────────────────────────────────────────────────────────────
def main() -> None:
    _set_timer_resolution()

    # 启动键盘监听线程
    t = threading.Thread(target=_keyboard_listener, daemon=True)
    t.start()

    # 加载配置
    try:
        with open("config.toml", "rb") as f:
            cfg = tomllib.load(f)
    except FileNotFoundError:
        print("[错误] 找不到 config.toml，请确认文件与 main.py 在同一目录")
        sys.exit(1)

    T1_str: str = cfg["timing"]["T1"]
    T2: float = float(cfg["timing"]["T2"])
    ls: float = float(cfg["timing"]["lead_seconds"])
    P1: tuple[int, int] = tuple(cfg["coordinates"]["P1"])  # type: ignore[assignment]
    P2: tuple[int, int] = tuple(cfg["coordinates"]["P2"])  # type: ignore[assignment]

    T1_dt = datetime.strptime(T1_str, "%Y-%m-%d %H:%M:%S")
    T1_ts = T1_dt.timestamp()
    start_ts = T1_ts - ls

    print("─" * 50)
    print(f"  目标时间 T1 : {T1_str}")
    print(f"  提前量   ls : {ls}s")
    print(f"  Phase 1  T2 : {T2}s  → 只点击 P1{P1}")
    print(f"  Phase 2     : 轮流点击 P1{P1} / P2{P2}（Ctrl+C 或 q 停止）")
    print(f"  控制键      : v=暂停  c=继续  q=退出")
    print("─" * 50)

    # 连接设备（提前连接，避免占用点击时间）
    print("正在连接 Android 设备 ...")
    d = u2.connect()
    print(f"已连接：{d.info.get('productName', '未知设备')}")

    try:
        if _quit.is_set():
            return

        # 倒计时 + 精确等待
        countdown(start_ts)
        if not _quit.is_set():
            wait_until(start_ts)

        # ── Phase 1：只点 P1 ──
        if not _quit.is_set():
            phase1_start = time.time()
            print(f"[Phase 1] 开始  {datetime.now().strftime('%H:%M:%S.%f')[:-3]}  → 点击 P1{P1}")
            c1 = click_phase(d, [P1], T2)
            phase1_elapsed = time.time() - phase1_start
            print(f"[Phase 1] 结束  共 {c1} 次  ({c1/phase1_elapsed:.1f} 次/秒)")

        # ── Phase 2：P1 / P2 轮流 ──
        if not _quit.is_set():
            print(f"[Phase 2] 开始  {datetime.now().strftime('%H:%M:%S.%f')[:-3]}  → 轮流 P1{P1} P2{P2}  (p暂停/q退出)")
            phase2_start = time.time()
            c2 = click_infinite(d, [P1, P2])
            phase2_elapsed = time.time() - phase2_start
            print(f"\n[Phase 2] 结束  共 {c2} 次  ({c2/phase2_elapsed:.1f} 次/秒)")
    except KeyboardInterrupt:
        print("\n已中断。")
    finally:
        _quit.set()
        _running.set()
        _restore_timer_resolution()
        print("完成。")


if __name__ == "__main__":
    main()

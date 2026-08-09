import argparse
import concurrent.futures
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config.example.json"
SCREENSHOT_DIR = ROOT / "screenshots"
LOG_DIR = ROOT / "logs"


COMMON_ADB_PATHS = [
    r"C:\Program Files\Netease\MuMu Player 12\shell\adb.exe",
    r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
    r"C:\Program Files\Netease\MuMu Player\emulator\nemu\vmonitor\bin\adb_server.exe",
    r"C:\Program Files (x86)\Netease\MuMu Player\emulator\nemu\vmonitor\bin\adb_server.exe",
]


print_lock = threading.Lock()


def now_stamp():
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def log(message):
    with print_lock:
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def load_config(path):
    if path is None:
        path = DEFAULT_CONFIG
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"找不到配置文件: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_adb(config):
    env_adb = os.environ.get("ADB_PATH")
    candidates = [
        config.get("adb_path"),
        env_adb,
        shutil.which("adb"),
        shutil.which("adb.exe"),
    ]
    candidates.extend(COMMON_ADB_PATHS)

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))

    raise RuntimeError(
        "没有找到 adb。请在 config.example.json 里填写 adb_path，"
        "或把 adb.exe 加入 PATH，或设置环境变量 ADB_PATH。"
    )


def parse_ports(value):
    ports = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            ports.extend(range(int(start), int(end) + 1))
        else:
            ports.append(int(part))
    return sorted(set(ports))


def run_adb(adb, args, timeout=20, binary=False):
    command = [adb] + args
    if binary:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def list_devices(adb):
    result = run_adb(adb, ["devices"], timeout=15)
    if result.returncode != 0:
        raise RuntimeError(f"adb devices 失败:\n{result.stderr}")

    devices = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def connect_ports(adb, ports):
    connected = []
    for port in ports:
        target = f"127.0.0.1:{port}"
        result = run_adb(adb, ["connect", target], timeout=8)
        output = f"{result.stdout}\n{result.stderr}".lower()
        if "connected" in output or "already connected" in output:
            connected.append(target)
    return connected


def wait_for_new_devices(adb, before_devices, timeout_seconds=120, poll_seconds=2):
    deadline = time.time() + timeout_seconds
    before_set = set(before_devices)
    while time.time() < deadline:
        current = list_devices(adb)
        new_devices = [device for device in current if device not in before_set]
        if new_devices:
            return new_devices
        time.sleep(poll_seconds)
    return []


def adb_device(adb, serial, args, timeout=20, binary=False):
    return run_adb(adb, ["-s", serial] + args, timeout=timeout, binary=binary)


def ensure_dirs():
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)


def take_screenshot(adb, serial, output_path):
    result = adb_device(adb, serial, ["exec-out", "screencap", "-p"], timeout=20, binary=True)
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    output_path.write_bytes(result.stdout)
    return output_path


def tap(adb, serial, x, y):
    result = adb_device(adb, serial, ["shell", "input", "tap", str(x), str(y)], timeout=10)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def swipe(adb, serial, x1, y1, x2, y2, duration_ms=300):
    result = adb_device(
        adb,
        serial,
        ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)],
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


def get_screen_size(adb, serial):
    result = adb_device(adb, serial, ["shell", "wm", "size"], timeout=10)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    for token in result.stdout.replace("\r", "").split():
        if "x" in token and token.replace("x", "").isdigit():
            width, height = token.split("x", 1)
            return int(width), int(height)
    return None


def detect_state(_screenshot_path):
    # MVP 先只提供稳定的流程骨架；后续可以在这里接 OpenCV 模板匹配或 OCR。
    return "unknown"


def run_once(adb, serial, config):
    device_dir = SCREENSHOT_DIR / serial.replace(":", "_")
    device_dir.mkdir(exist_ok=True)
    shot_path = device_dir / f"{now_stamp()}.png"
    take_screenshot(adb, serial, shot_path)
    state = detect_state(shot_path)

    if config.get("tap_center_after_screenshot", False):
        size = get_screen_size(adb, serial)
        if size:
            tap(adb, serial, size[0] // 2, size[1] // 2)
            return f"截图完成: {shot_path.name}, state={state}, 已点击中心点"

    return f"截图完成: {shot_path.name}, state={state}"


def device_worker(adb, serial, config, loops):
    interval = float(config.get("loop_interval_seconds", 3))
    failures = 0
    max_failures = int(config.get("max_failures", 3))

    for index in range(1, loops + 1):
        try:
            message = run_once(adb, serial, config)
            failures = 0
            log(f"[{serial}] 第 {index}/{loops} 轮: {message}")
        except Exception as exc:
            failures += 1
            log(f"[{serial}] 第 {index}/{loops} 轮失败({failures}/{max_failures}): {exc}")
            if failures >= max_failures:
                log(f"[{serial}] 连续失败过多，已停止这个模拟器，其他模拟器继续运行。")
                return
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="MuMu 多开 ADB 自动化 MVP")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="配置文件路径")
    parser.add_argument("--loops", type=int, default=1, help="每个模拟器执行几轮")
    parser.add_argument("--serial", action="append", help="只运行指定设备，可重复传入")
    parser.add_argument("--list", action="store_true", help="只列出 ADB 设备")
    parser.add_argument("--connect-ports", help="扫描并连接本机端口，例如 16384-16500 或 16384,16416")
    parser.add_argument("--wait-new", action="store_true", help="等待新启动的模拟器 ADB 设备出现")
    parser.add_argument("--wait-timeout", type=int, default=120, help="等待新设备的最长秒数")
    args = parser.parse_args()

    ensure_dirs()
    config = load_config(args.config)
    adb = find_adb(config)
    log(f"使用 ADB: {adb}")

    if args.connect_ports:
        ports = parse_ports(args.connect_ports)
        connected = connect_ports(adb, ports)
        log(f"端口连接完成，成功 {len(connected)} 个: {', '.join(connected) or '无'}")

    before_devices = list_devices(adb)
    if args.wait_new:
        log(f"当前已有设备 {len(before_devices)} 个，正在等待新设备出现...")
        new_devices = wait_for_new_devices(adb, before_devices, timeout_seconds=args.wait_timeout)
        if not new_devices:
            log("等待超时，没有发现新设备。")
            return 1
        log(f"发现新设备: {', '.join(new_devices)}")
        args.serial = (args.serial or []) + new_devices

    configured_devices = config.get("devices") or []
    devices = args.serial or configured_devices or list_devices(adb)

    if args.list:
        for device in list_devices(adb):
            print(device)
        return 0

    if not devices:
        log("没有发现在线设备。请先启动 MuMu 多开，并确认 ADB 已连接。")
        return 1

    max_workers = int(config.get("max_workers", min(9, len(devices))))
    log(f"准备控制 {len(devices)} 个模拟器，并发数 {max_workers}: {', '.join(devices)}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(device_worker, adb, serial, config, args.loops)
            for serial in devices
        ]
        for future in concurrent.futures.as_completed(futures):
            future.result()

    log("全部任务结束。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

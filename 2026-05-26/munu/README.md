# MuMu 多开自动化 MVP

这是一个最小可用版本，目标是先打通 9 个 MuMu 模拟器的独立控制底座：

- 自动发现 ADB 在线设备
- 给每个模拟器单独截图
- 并发控制多个模拟器
- 单个模拟器失败不会影响其他模拟器
- 可选：截图后点击屏幕中心点

## 1. 准备

先启动 MuMu 多开实例，并打开游戏。

如果脚本找不到 ADB，请编辑 `config.example.json`，把 `adb_path` 改成你的 ADB 路径，例如：

```json
{
  "adb_path": "C:\\Program Files\\Netease\\MuMu Player 12\\shell\\adb.exe"
}
```

也可以设置环境变量 `ADB_PATH`。

## 2. 查看设备

如果你电脑已经安装 Python，使用：

```powershell
py .\mumu_mvp.py --list
```

如果 `py` 提示没有安装 Python，可以先用 Codex 自带 Python 跑：

```powershell
C:\Users\21778\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe .\mumu_mvp.py --list
```

如果看到类似下面的设备编号，就说明 ADB 已经通了：

```text
127.0.0.1:16384
127.0.0.1:16416
```

## 3. 给所有模拟器截图

```powershell
py .\mumu_mvp.py --loops 1
```

截图会保存到：

```text
screenshots/
```

## 4. 连续运行多轮

```powershell
py .\mumu_mvp.py --loops 10
```

每个模拟器会独立执行：

```text
截图 -> 判断状态 -> 等待 -> 下一轮
```

当前 `detect_state()` 先返回 `unknown`，这是后续接图像识别的位置。

## 5. 测试点击

把 `config.example.json` 里的这一项改成 `true`：

```json
"tap_center_after_screenshot": true
```

然后运行：

```powershell
py .\mumu_mvp.py --loops 1
```

脚本会对每个模拟器截图后点击屏幕中心点。

## 6. 只控制指定模拟器

```powershell
py .\mumu_mvp.py --serial 127.0.0.1:16384 --loops 3
```

也可以在 `config.example.json` 的 `devices` 里固定设备列表：

```json
"devices": [
  "127.0.0.1:16384",
  "127.0.0.1:16416"
]
```

## 7. 动态端口和新设备

如果你的每个小号都是新建模拟器，ADB 端口会变，不要把端口写死。流程应该是：

```text
启动前记录已有 ADB 设备 -> 创建/启动新 MuMu 实例 -> 等待新的 ADB 设备出现 -> 把新设备加入自动化
```

脚本已经支持等待新设备：

```powershell
py .\mumu_mvp.py --wait-new --wait-timeout 180 --loops 1
```

使用方法：

1. 先运行上面的命令。
2. 再去 MuMu 多开器里创建/启动一个新模拟器。
3. 脚本会等待新的 ADB 设备出现，并只操作这个新设备。

如果 MuMu 实例已经启动但没有自动出现在 `adb devices`，可以扫描连接一个端口范围：

```powershell
py .\mumu_mvp.py --connect-ports 16384-16600 --list
```

也可以指定离散端口：

```powershell
py .\mumu_mvp.py --connect-ports 16384,16416,16448 --list
```

端口随机时，建议用“等待新设备”为主；只有在 `adb devices` 不自动出现时，再用端口扫描连接。

## 下一步建议

下一步应该在 `detect_state()` 里加入图像识别，例如识别“开始游戏”“公告关闭”“重连”等按钮。识别成功后，再根据状态调用 `tap()` 或 `swipe()`。

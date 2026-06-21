# 升级 scrcpy-server.jar 至 4.0 版本

> **日期**: 2026-06-21
> **问题**: 日志显示 `从 JAR 检测到 scrcpy server 版本: 3.3.4`，说明 JAR 文件未替换

---

## 一、问题分析

### 根因

上一轮迁移只修改了 **代码逻辑**（版本检测默认值、协议解析兼容性等），但没有替换实际的 **二进制资源文件**：

| 资源 | 当前状态 | 目标状态 |
|-----|---------|---------|
| `lib/scrcpy-server.jar` | **3.3.4** (90,982 bytes) | **4.0** |
| `lib/scrcpy-win64/` | 旧版工具集 | 4.0 工具集 |

### 影响链路

```
代码已适配 4.0 ✅
    ↓
但 JAR 文件仍是 3.3.4 ❌
    ↓
_detect_server_jar_version() → 返回 "3.3.4"
    ↓
_read_scrcpy_header() → 走 3.x 分支（而非 4.x）
    ↓
_start_server_process() → 传 version="3.3.4" 给 server
    ↓
日志: "从 JAR 检测到 scrcpy server 版本: 3.3.4"
```

### 关键约束（来自官方文档）

> The server fails if the client and the server do not have the **exact same version**.
>
> — [scrcpy develop.md](https://github.com/Genymobile/scrcpy/blob/master/doc/develop.md)

**Client 和 Server 必须版本完全一致**，否则 server 会拒绝启动或行为异常。

---

## 二、实施方案

### 步骤 1：下载 scrcpy 4.0 正式版

**来源**: [GitHub Releases v4.0](https://github.com/Genymobile/scrcpy/releases/tag/v4.0)

**需要下载的文件**:
- `scrcpy-win64-v4.0.zip` (Windows 64位完整包)

**SHA-256 校验**: 从 Release 页面获取，下载后验证完整性

### 步骤 2：提取并部署资源

解压 `scrcpy-win64-v4.0.zip` 后：

```
scrcpy-win64-v4.0/
├── scrcpy.exe              # 客户端可执行文件
├── scrcpy-server.jar        # ← 目标文件：4.0 版本 server JAR
├── scrcpy-console.bat
├── scrcpy-noconsole.vbs
└── ... (其他文件)
```

**部署操作**:

```powershell
# 1. 备份当前 JAR（回退用）
Copy-Item d:\Github\PY\lib\scrcpy-server.jar d:\Github\PY\lib\scrcpy-server-v3.3.4.jar

# 2. 替换 JAR 文件
# 从下载的 zip 中提取 scrcpy-server.jar 到 lib/
Copy-Item <extract_path>\scrcpy-server.jar d:\Github\PY\lib\scrcpy-server.jar -Force

# 3. 替换 win64 工具目录
Remove-Item d:\Github\PY\lib\scrcpy-win64\ -Recurse -Force
Copy-Item <extract_path>\* d:\Github\PY\lib\scrcpy-win64\ -Recurse
```

### 步骤 3：验证部署结果

**验证清单**:
- [ ] JAR 文件大小变化（4.0 应 > 90KB）
- [ ] `_detect_server_jar_version()` 返回含 "4" 的版本号
- [ ] 日志输出: `从 JAR 检测到 scrcpy server 版本: 4.x.x`
- [ ] 单元测试全部通过

### 步骤 4：运行测试确认功能正常

```bash
cd d:/Github/PY
python -m pytest tests/test_screen_capture.py tests/test_performance_benchmark.py -v --tb=short
```

---

## 三、涉及文件变更

| 文件 | 操作 | 说明 |
|-----|------|------|
| `lib/scrcpy-server.jar` | **替换** | 3.3.4 → 4.0 |
| `lib/scrcpy-server-v3.3.4.jar` | **新建** | 备份旧版（回滚用） |
| `lib/scrcpy-win64/*` | **全部替换** | 升级到 4.0 工具集 |

> 注意：**不需要修改任何 Python 代码**，代码已在上一轮完成适配。

---

## 四、回滚方案

如果 4.0 出现问题，快速回滚：

```powershell
# 恢复旧版 JAR
Copy-Item d:\Github\PY\lib\scrcpy-server-v3.3.4.jar d:\Github\PY\lib\scrcpy-server.jar -Force
```

预计耗时：< 10 秒

---

## 五、验证方法

### 自动化验证

运行新增的版本检测测试：
```bash
python -m pytest tests/test_performance_benchmark.py::TestScrcpy4VersionDetection -v
```

预期结果：`test_parse_major_version_v4` PASSED（检测到 major=4）

### 手动验证

连接 Android 设备后观察日志：
```
[INFO] 从 JAR 检测到 scrcpy server 版本: 4.0.0   # ← 应该出现这个
[INFO] scrcpy 4.x 协议: 设备=xxx, codec=0x68323634, 分辨率=xxx  # ← 应该走 4.x 分支
```

而不是：
```
[INFO] 从 JAR 检测到 scrcpy server 版本: 3.3.4   # ← 当前（错误）状态
[INFO] scrcpy 3.x 协议: 设备=xxx, ...
```

---

## 六、假设与决策

| 假设 | 状态 | 风险应对 |
|-----|------|---------|
| 用户可访问 GitHub 下载 Releases | 待确认 | 如无法访问，需提供替代下载源 |
| scrcpy 4.0 JAR 与 3.3.4 协议向后兼容 | 已在代码中处理 | 代码已支持 2.x/3.x/4.x 自适应 |
| 项目有网络访问权限用于下载 | 待确认 | 可手动下载后放到指定路径 |

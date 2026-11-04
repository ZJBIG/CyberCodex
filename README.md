# CyberCodex

Windows Codex 的可回退赛博朋克主题：紫色玻璃界面、霓虹横幅、每两分钟轮换的背景视频，以及审核按钮样式。

- `ThemeTools/patch_asar_theme.py`：发现 ASAR 中的界面入口、备份并写入主题。
- `ThemeTools/theme.css`、`theme-runtime.js`：从当前运行版本整理出的样式和脚本模板。
- `ThemeTools/cyberpunk-assets/Cyberpunk/Textures/`：实际使用的两张图片和五段视频。
- `Launchers/回退到官方Codex.ps1`：打开已安装的 Microsoft Store 官方版。
- `tests/`：归档内容保留、重复执行、失败回退和相对路径验证。

需要 Python 3，以及一份可写的 Codex Windows 应用副本。应用运行文件和本机 Profile 另行保留，不随源码发布。已核对本地 `App-26.915.3509.0`；其他版本的入口结构需单独验证。

先关闭主题应用，再从仓库根目录执行：

```powershell
$themeArchive = 'D:\CyberCodex\App-26.915.3509.0\resources\app.asar'
$themeAssets = 'ThemeTools\cyberpunk-assets\Cyberpunk\Textures'
python ThemeTools/patch_asar_theme.py $themeArchive `
  "$themeAssets\UI_BackgroundMain.BGPlanet@8.jpg" - `
  "$themeAssets\UI_BackgroundMain.BGPlanet@3.jpg" `
  "$themeAssets\UI_BackgroundMain.BGPlanet.webm" -
```

`icon`、`cursor` 两个位置保留以兼容旧命令，当前主题填 `-` 即可。脚本自动收集同目录中以 `UI_BackgroundMain.BGPlanet` 开头的 WebM 视频。

首次执行创建 `app.asar.official`，后续始终从该备份重建，避免重复叠加。恢复此应用副本时，关闭应用后执行：

```powershell
Copy-Item -LiteralPath "$themeArchive.official" -Destination $themeArchive -Force
```

运行针对性检查：

```powershell
python -B -m unittest discover -s tests -v
```

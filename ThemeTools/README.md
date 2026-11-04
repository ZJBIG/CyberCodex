# 主题源码

`patch_asar_theme.py` 负责归档处理；`theme.css` 和 `theme-runtime.js` 保存现用主题模板。模板由 Python 标准库 `string.Template` 填入图片和视频数据，无额外依赖。

素材仅发布当前主题使用的 `Textures/UI_BackgroundMain.BGPlanet@3.jpg`、`@8.jpg` 和五段同名前缀 WebM。其他本地素材由 `.gitignore` 排除。

应用、回退和验证命令见[仓库说明](../README.md)。

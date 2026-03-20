# 贴图转 DTX 工具说明

## 工具用途

这个工具包包含：

- `texture_to_dtx_converter.exe`
  批量将 `bmp`、`jpg`、`jpeg`、`png`、`tga` 贴图转换为 `dtx`
- `relink_project_textures_to_dtx.ms`
  3ds Max 脚本，用于把场景中的位图贴图重定向到项目目录里已有的 `.dtx` 文件


## 转换器功能说明

`texture_to_dtx_converter.exe` 的行为如下：

- 扫描 exe 所在目录及其所有子目录
- 支持 `bmp`、`jpg`、`jpeg`、`png`、`tga`
- 自动跳过 `output_dtx`、`dist`、`build`、`__pycache__` 目录
- 超过 `1024` 的贴图会自动缩小
- 非正方形或非 2 次幂尺寸的贴图会自动补成兼容的正方形 2 次幂尺寸
- 如果源图包含透明像素，生成的 `.dtx` 会自动写入 `alpharef 128`
- 输出结果统一放到 `output_dtx` 目录
- 保留原始目录结构
- 运行时显示进度窗口
- 生成日志文件 `convert_to_dtx.log`

## 使用方法

### 1. 批量转换贴图

1. 把 `texture_to_dtx_converter.exe` 放到贴图根目录
2. 确保同目录下有：
   `dtxutil.exe`
   `MFC71.dll`
   `msvcr71.dll`
3. 双击运行 exe
4. 等待进度窗口处理完成
5. 到生成的 `output_dtx` 目录查看结果

### 2. 在 3ds Max 里重定向贴图

1. 在 3ds Max 里运行 `relink_project_textures_to_dtx.ms`
2. 选择已经包含 `.dtx` 文件的项目贴图目录
3. 点击 `Relink`

## 说明

- Max 脚本只负责重定向已有的 `.dtx` 文件，不会执行转换
- 匹配方式基于“贴图文件名去掉扩展名”
- 如果不同目录下存在同名 `.dtx`，脚本只会使用第一个找到的文件


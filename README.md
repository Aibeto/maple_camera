# 汐沃视频展台
## 下载 download
[下载](https://github.com/wwcrdrvf6u/ShowWrite/releases/)

## 加入我们
![QQ交流群](讨论群.jpg)
## 文件目录结构

```
EasiCamera【版本号】/
├── easicamera.py             # 主程序文件
├── boot.JPG                  # 启动背景图片
├── config.json               # 配置文件（程序运行后生成）
├── icons/                    # 图标目录
│   ├── pen.png               # 画笔图标
│   ├── switch_camera.png     # 切换摄像头图标
│   ├── capture.png           # 拍照图标
│   ├── save.png              # 保存图标
│   ├── move.png              # 移动工具图标
│   ├── eraser.png            # 橡皮擦图标
│   ├── clear.png             # 清除图标
│   ├── undo.png              # 撤回图标
│   ├── settings.png          # 设置图标（画笔设置）
│   ├── correction.png        # 梯形校正图标
│   ├── adjust.png            # 画面调节图标
│   ├── photos.png            # 照片库图标
│   ├── minimize.png          # 最小化图标
│   ├── exit.png              # 退出图标
│   └── scan.png              # 应用图标（窗口图标）
└── captures/                 # 照片保存目录（程序运行时自动创建）
    ├── capture_20231025_143022.png
    ├── capture_20231025_143145.jpg
    └── ...
```

## 使用说明
### 快捷键：
- 空格键：拍照
- P键：画笔工具
- M键：移动工具
- E键：橡皮擦工具
- Ctrl+Z：撤回操作
- Ctrl+S：保存当前画面
- Esc：退出软件

## 运行要求
- Python 3.6+
- 依赖库：`opencv-python`, `numpy`, `PySide2`, `Pillow`
- 操作系统：Windows7、10、11

## 安装指南
1. 安装Python 3.6或更高版本
2. 安装依赖库：
```
pip install opencv-python numpy PySide2
pip install Pillow==9.5.0
```

4. 下载软件文件到本地目录
5. 运行主程序：
      python easicamera.py
   

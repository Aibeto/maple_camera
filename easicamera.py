import sys
import cv2
import numpy as np
import os
import platform
import json
import math
import threading
import time
from datetime import datetime
from PySide2.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, 
                            QPushButton, QHBoxLayout, QSlider, QSizePolicy, QAction, 
                            QToolBar, QStatusBar, QFileDialog, QColorDialog, QMessageBox,
                            QDialog, QGridLayout, QGroupBox, QScrollArea, QFrame, 
                            QListWidget, QListWidgetItem, QSplitter, QDockWidget, 
                            QCheckBox, QSpinBox, QDoubleSpinBox, QButtonGroup, QRadioButton,
                            QSizeGrip, QComboBox, QMenu)
from PySide2.QtGui import (QImage, QPixmap, QPainter, QPen, QColor, QFont, QIcon, 
                         QTransform, QKeySequence, QPalette, QBrush, QMouseEvent,
                         QPainterPath, QRegion, QCursor, QFontMetrics, QPainter, QPaintEvent)
from PySide2.QtCore import Qt, QTimer, QPointF, QEvent, QSize, QRect, QPoint, QCoreApplication, Signal, QThread, QObject

# 高DPI适配
if platform.system() == "Windows":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

class CameraInitThread(QThread):
    """摄像头初始化线程"""
    finished = Signal(object)  # 返回摄像头对象
    error = Signal(str)
    
    def __init__(self, camera_index, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
    
    def run(self):
        cap = None
        try:
            # 尝试多种分辨率
            resolutions = [(1920, 1080), (1280, 720), (640, 480)]
            
            for res in resolutions:
                try:
                    if platform.system() == "Windows":
                        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                    else:
                        cap = cv2.VideoCapture(self.camera_index)
                        
                    if cap.isOpened():
                        # 尝试设置分辨率
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, res[0])
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, res[1])
                        
                        # 检查实际分辨率
                        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        
                        # 如果设置成功
                        if actual_width >= res[0] and actual_height >= res[1]:
                            self.finished.emit(cap)
                            return
                except Exception as e:
                    print(f"摄像头初始化错误: {e}")
            
            # 如果所有分辨率都失败
            if cap:
                cap.release()
            self.error.emit(f"无法初始化摄像头 {self.camera_index}")
        except Exception as e:
            self.error.emit(f"摄像头初始化错误: {str(e)}")
            if cap:
                cap.release()

class ColorWidthDialog(QDialog):
    """画笔设置对话框"""
    def __init__(self, parent=None, current_color=QColor(255, 0, 0), current_width=3):  # 默认粗细改为3px
        super().__init__(parent)
        self.setWindowTitle("画笔设置")
        self.setWindowIcon(QIcon("icons/pen.png"))
        self.setFixedSize(300, 200)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 颜色选择部分
        color_group = QGroupBox("颜色")
        color_layout = QHBoxLayout()
        color_layout.setContentsMargins(5, 10, 5, 10)
        
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(40, 40)
        self.set_button_color(current_color)
        self.color_btn.clicked.connect(self.select_color)
        color_layout.addWidget(self.color_btn)
        
        # 颜色值标签
        self.color_label = QLabel(current_color.name())
        self.color_label.setFixedHeight(30)
        self.color_label.setAlignment(Qt.AlignCenter)
        self.color_label.setStyleSheet(f"""
            QLabel {{
                background-color: {current_color.name()};
                color: white;
                border-radius: 5px;
                font-size: 12px;
                padding: 3px;
            }}
        """)
        color_layout.addWidget(self.color_label)
        color_group.setLayout(color_layout)
        
        # 画笔粗细部分
        width_group = QGroupBox("画笔粗细")
        width_layout = QVBoxLayout()
        width_layout.setContentsMargins(5, 10, 5, 5)
        
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(1, 15)  # 范围1-15px
        self.width_slider.setValue(current_width)
        self.width_slider.valueChanged.connect(self.update_width_label)
        width_layout.addWidget(self.width_slider)
        
        self.width_label = QLabel(f"当前粗细: {current_width}px")
        self.width_label.setAlignment(Qt.AlignCenter)
        self.width_label.setStyleSheet("font-size: 12px;")
        width_layout.addWidget(self.width_label)
        width_group.setLayout(width_layout)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        ok_btn = QPushButton("确定")
        ok_btn.setFixedHeight(30)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(30)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        
        # 添加到主布局
        layout.addWidget(color_group)
        layout.addWidget(width_group)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # 存储当前设置
        self.selected_color = current_color
        self.selected_width = current_width
    
    def set_button_color(self, color):
        """设置按钮颜色"""
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color.name()};
                border: 1px solid #cccccc;
                border-radius: 20px;
            }}
            QPushButton:hover {{
                border: 1px solid #3498db;
            }}
        """)
    
    def select_color(self):
        """选择颜色"""
        color = QColorDialog.getColor(self.selected_color, self)
        if color.isValid():
            self.selected_color = color
            self.set_button_color(color)
            self.color_label.setText(color.name())
            self.color_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {color.name()};
                    color: white;
                    border-radius: 5px;
                    font-size: 12px;
                    padding: 3px;
                }}
            """)
    
    def update_width_label(self, width):
        """更新粗细标签"""
        self.selected_width = width
        self.width_label.setText(f"当前粗细: {width}px")
    
    def get_settings(self):
        """获取设置"""
        return self.selected_color, self.selected_width

class PerspectiveCorrectionDialog(QDialog):
    """梯形校正对话框"""
    def __init__(self, parent=None, points=None, background_pixmap=None, resolution=(1920, 1080)):
        super().__init__(parent)
        self.setWindowTitle("梯形校正")
        self.setFixedSize(800, 600)
        
        # 默认校正点（归一化坐标）
        default_points = [
            QPointF(0.1, 0.1), 
            QPointF(0.9, 0.1), 
            QPointF(0.9, 0.9), 
            QPointF(0.1, 0.9)
        ]
        
        self.points = points if points else default_points
        self.resolution = resolution
        self.selected_point = -1
        self.point_radius = 10
        self.background_pixmap = background_pixmap
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 显示区域
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(600, 400)
        self.image_label.setStyleSheet("background-color: #2c2c2c; border: 1px solid #444;")
        layout.addWidget(self.image_label)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        
        reset_btn = QPushButton("重置")
        reset_btn.setFixedSize(80, 30)
        reset_btn.clicked.connect(self.reset_points)
        btn_layout.addWidget(reset_btn)
        
        apply_btn = QPushButton("应用")
        apply_btn.setFixedSize(80, 30)
        apply_btn.clicked.connect(self.accept)
        btn_layout.addWidget(apply_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 30)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        # 创建示例图像
        self.update_example_image()
        
        # 安装事件过滤器
        self.image_label.installEventFilter(self)
    
    def update_example_image(self):
        """更新示例图像（使用当前视频帧作为背景）"""
        img = QImage(800, 600, QImage.Format_RGB32)
        
        if self.background_pixmap and not self.background_pixmap.isNull():
            # 使用当前视频帧作为背景
            background = self.background_pixmap.scaled(
                800, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            
            # 创建临时图像用于绘制
            img = QImage(800, 600, QImage.Format_RGB32)
            painter = QPainter(img)
            
            # 绘制背景（稍微变暗以便看清网格和点）
            painter.setOpacity(0.7)
            painter.drawPixmap(0, 0, background)
            painter.setOpacity(1.0)
            
            # 绘制网格（半透明）
            painter.setPen(QPen(QColor(100, 100, 100, 150), 1))
            for i in range(0, 800, 40):
                painter.drawLine(i, 0, i, 600)
            for i in range(0, 600, 40):
                painter.drawLine(0, i, 800, i)
            
            # 绘制校正点
            painter.setBrush(QBrush(QColor(255, 0, 0, 200)))
            for i, point in enumerate(self.points):
                x = int(point.x() * 800)
                y = int(point.y() * 600)
                painter.drawEllipse(QPoint(x, y), self.point_radius, self.point_radius)
                painter.drawText(x + 15, y + 5, f"{i+1}")
            
            # 绘制连接线
            painter.setPen(QPen(QColor(0, 255, 0, 200), 2))
            for i in range(4):
                x1 = int(self.points[i].x() * 800)
                y1 = int(self.points[i].y() * 600)
                x2 = int(self.points[(i+1)%4].x() * 800)
                y2 = int(self.points[(i+1)%4].y() * 600)
                painter.drawLine(x1, y1, x2, y2)
            
            painter.end()
        else:
            # 没有背景图像时使用默认灰色背景
            img.fill(Qt.darkGray)
            
            painter = QPainter(img)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 绘制网格
            painter.setPen(QPen(QColor(100, 100, 100), 1))
            for i in range(0, 800, 40):
                painter.drawLine(i, 0, i, 600)
            for i in range(0, 600, 40):
                painter.drawLine(0, i, 800, i)
            
            # 绘制校正点
            painter.setBrush(QBrush(QColor(255, 0, 0)))
            for i, point in enumerate(self.points):
                x = int(point.x() * 800)
                y = int(point.y() * 600)
                painter.drawEllipse(QPoint(x, y), self.point_radius, self.point_radius)
                painter.drawText(x + 15, y + 5, f"{i+1}")
            
            # 绘制连接线
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            for i in range(4):
                x1 = int(self.points[i].x() * 800)
                y1 = int(self.points[i].y() * 600)
                x2 = int(self.points[(i+1)%4].x() * 800)
                y2 = int(self.points[(i+1)%4].y() * 600)
                painter.drawLine(x1, y1, x2, y2)
            
            painter.end()
        
        self.image_label.setPixmap(QPixmap.fromImage(img))
    
    def reset_points(self):
        """重置校正点"""
        self.points = [
            QPointF(0.1, 0.1), 
            QPointF(0.9, 0.1), 
            QPointF(0.9, 0.9), 
            QPointF(0.1, 0.9)
        ]
        self.update_example_image()
    
    def eventFilter(self, source, event):
        """事件过滤器处理鼠标事件"""
        if source == self.image_label:
            if event.type() == QEvent.MouseButtonPress:
                pos = event.pos()
                for i, point in enumerate(self.points):
                    img_x = int(point.x() * 800)
                    img_y = int(point.y() * 600)
                    if (pos - QPoint(img_x, img_y)).manhattanLength() < self.point_radius * 2:
                        self.selected_point = i
                        return True
            elif event.type() == QEvent.MouseMove and self.selected_point >= 0:
                pos = event.pos()
                # 限制在图像范围内
                x = max(0, min(pos.x(), 800)) / 800
                y = max(0, min(pos.y(), 600)) / 600
                self.points[self.selected_point] = QPointF(x, y)
                self.update_example_image()
                return True
            elif event.type() == QEvent.MouseButtonRelease:
                self.selected_point = -1
                return True
        return super().eventFilter(source, event)
    
    def get_points(self):
        """获取校正点（实际像素坐标）"""
        return [
            QPointF(self.points[0].x() * self.resolution[0], self.points[0].y() * self.resolution[1]),
            QPointF(self.points[1].x() * self.resolution[0], self.points[1].y() * self.resolution[1]),
            QPointF(self.points[2].x() * self.resolution[0], self.points[2].y() * self.resolution[1]),
            QPointF(self.points[3].x() * self.resolution[0], self.points[3].y() * self.resolution[1])
        ]

class ImageAdjustmentDialog(QDialog):
    """画面调节对话框"""
    def __init__(self, parent=None, brightness=100, contrast=100, orientation=0, flip_horizontal=False):
        super().__init__(parent)
        self.setWindowTitle("画面调节")
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 亮度调节
        brightness_group = QGroupBox("亮度")
        brightness_layout = QVBoxLayout()
        
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(0, 200)
        self.brightness_slider.setValue(brightness)
        self.brightness_slider.valueChanged.connect(self.update_brightness_label)
        brightness_layout.addWidget(self.brightness_slider)
        
        self.brightness_label = QLabel(f"亮度: {brightness}%")
        self.brightness_label.setAlignment(Qt.AlignCenter)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        
        # 对比度调节
        contrast_group = QGroupBox("对比度")
        contrast_layout = QVBoxLayout()
        
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(0, 200)
        self.contrast_slider.setValue(contrast)
        self.contrast_slider.valueChanged.connect(self.update_contrast_label)
        contrast_layout.addWidget(self.contrast_slider)
        
        self.contrast_label = QLabel(f"对比度: {contrast}%")
        self.contrast_label.setAlignment(Qt.AlignCenter)
        contrast_layout.addWidget(self.contrast_label)
        contrast_group.setLayout(contrast_layout)
        
        # 方向调整
        orientation_group = QGroupBox("方向")
        orientation_layout = QHBoxLayout()
        
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItem("竖向 (0°)", 0)
        self.orientation_combo.addItem("横向 (90°)", 90)
        self.orientation_combo.addItem("倒立 (180°)", 180)
        self.orientation_combo.addItem("横向 (270°)", 270)
        self.orientation_combo.setCurrentIndex(orientation)
        orientation_layout.addWidget(self.orientation_combo)
        orientation_group.setLayout(orientation_layout)
        
        # 镜像翻转
        flip_group = QGroupBox("镜像")
        flip_layout = QHBoxLayout()
        
        self.flip_checkbox = QCheckBox("水平翻转")
        self.flip_checkbox.setChecked(flip_horizontal)
        flip_layout.addWidget(self.flip_checkbox)
        flip_group.setLayout(flip_layout)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        apply_btn = QPushButton("应用")
        apply_btn.setFixedHeight(35)
        apply_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(35)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        
        # 添加到主布局
        layout.addWidget(brightness_group)
        layout.addWidget(contrast_group)
        layout.addWidget(orientation_group)
        layout.addWidget(flip_group)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def update_brightness_label(self, value):
        """更新亮度标签"""
        self.brightness_label.setText(f"亮度: {value}%")
    
    def update_contrast_label(self, value):
        """更新对比度标签"""
        self.contrast_label.setText(f"对比度: {value}%")
    
    def get_settings(self):
        """获取设置"""
        return {
            "brightness": self.brightness_slider.value(),
            "contrast": self.contrast_slider.value(),
            "orientation": self.orientation_combo.currentIndex(),
            "flip_horizontal": self.flip_checkbox.isChecked()
        }

class VideoAnnotationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 设置应用为全屏模式
        self.showFullScreen()
        
        # 设置窗口标题
        self.setWindowTitle("希沃视频展台（我写的）")
        self.setWindowIcon(QIcon("icons/scan.png"))  # 设置窗口图标
        
        # 触控初始化
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.pinch_zoom = 1.0
        self.pan_offset = QPointF(0, 0)
        self.last_touch_points = {}
        self.touch_drawing = False
        
        # 性能优化配置
        self.camera_resolution = (1280, 720)  # 默认分辨率
        self.target_fps = 30
        
        # 初始化变量
        self.cap = None
        self.current_frame = None
        self.drawing = False
        self.last_point = None
        self.annotations = []
        self.current_tool = "pen"
        self.pen_color = QColor(255, 0, 0)
        self.pen_width = 3  # 默认画笔粗细改为3px
        self.camera_active = False
        self.saved_image_path = None
        self.startup_image = None
        self.showing_startup = True
        self.current_camera_index = -1
        self.captured_images = []
        self.current_captured_image = None
        self.photo_dock = None
        self.zoom_factor = 1.0
        self.zoom_offset = QPointF(0, 0)
        self.current_annotation = None
        self.last_touch_area = 0.0
        self.palm_threshold = 1500
        self.camera_list = []
        self.arrow_start_point = None
        self.temp_annotation = None
        self.last_draw_time = 0
        self.zoom_indicator = None
        self.zoom_indicator_timer = None
        self.background_frame = None
        self.annotation_layer = None
        self.base_image = None
        self.perspective_points = []  # 梯形校正点
        self.camera_names = {}  # 摄像头型号映射
        self.image_adjustments = {  # 画面调节参数
            "brightness": 100,
            "contrast": 100,
            "orientation": 0,  # 0: 竖向, 1: 横向90°, 2: 倒立180°, 3: 横向270°
            "flip_horizontal": False
        }
        self.dragging = False
        self.drag_start_pos = QPointF()
        self.drag_current_pos = QPointF()
        
        # 加载配置
        self.load_config()
        
        # 创建UI
        self.init_ui()
        
        # 显示启动图
        self.show_startup_image()
        
        # 启动3秒计时器，然后自动连接摄像头
        self.startup_timer = QTimer(self)
        self.startup_timer.setSingleShot(True)
        self.startup_timer.timeout.connect(self.post_startup)
        self.startup_timer.start(3000)  # 启动图显示3秒
    
    def post_startup(self):
        """启动图显示3秒后执行的操作"""
        self.video_label.setPixmap(QPixmap())
        self.video_label.setStyleSheet("background-color: black;")
        self.showing_startup = False
        self.auto_connect_camera()
    
    def load_config(self):
        """加载配置文件"""
        self.config = {
            "camera_index": -1, 
            "camera_name": "",
            "perspective_points": [],
            "image_adjustments": {
                "brightness": 100,
                "contrast": 100,
                "orientation": 0,
                "flip_horizontal": False
            }
        }
        
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                    self.config = json.load(f)
                    self.current_camera_index = self.config.get("camera_index", -1)
                    
                    # 加载梯形校正点
                    perspective_points = self.config.get("perspective_points", [])
                    if perspective_points:
                        self.perspective_points = [QPointF(p['x'], p['y']) for p in perspective_points]
                    
                    # 加载画面调节设置
                    adjustments = self.config.get("image_adjustments", {})
                    if adjustments:
                        self.image_adjustments = adjustments
        except:
            pass
    
    def save_config(self):
        """保存配置文件"""
        try:
            self.config["camera_index"] = self.current_camera_index
            self.config["camera_name"] = self.camera_names.get(self.current_camera_index, "")
            
            # 保存梯形校正点
            if self.perspective_points and len(self.perspective_points) == 4:
                self.config["perspective_points"] = [
                    {"x": p.x(), "y": p.y()} for p in self.perspective_points
                ]
            else:
                self.config["perspective_points"] = []
            
            # 保存画面调节设置
            self.config["image_adjustments"] = self.image_adjustments
            
            with open("config.json", "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
        
    def init_ui(self):
        # 设置窗口背景色
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QDockWidget {
                background-color: #2c3e50;
                color: white;
                font-size: 12px;
                border: 1px solid #3498db;
            }
            QDockWidget::title {
                background-color: #2c3e50;
                text-align: left;
                padding-left: 8px;
            }
        """)
        
        # 创建主窗口部件
        main_widget = QWidget()
        main_widget.setStyleSheet("background-color: #1e1e1e;")
        self.setCentralWidget(main_widget)
        
        # 主布局
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 视频显示区域
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #000000;
                border: 1px solid #3498db;
                border-radius: 4px;
            }
        """)
        self.video_label.setMinimumSize(800, 600)
        
        # 安装事件过滤器来处理触控和鼠标事件
        self.video_label.installEventFilter(self)
        
        main_layout.addWidget(self.video_label, 1)
        
        # 创建底部工具栏
        self.toolbar = QToolBar("主工具栏")
        self.toolbar.setIconSize(QSize(24, 24))  # 减小图标大小
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.toolbar.setMovable(True)
        self.toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2c3e50;
                border-top: 1px solid #3498db;
                padding: 4px;
                spacing: 6px;
            }
            QToolButton {
                background-color: white;
                color: #2c3e50;
                border-radius: 4px;
                padding: 4px;
                font-size: 10px;
                min-width: 40px;
                min-height: 40px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
            QToolButton:pressed {
                background-color: #d0d0d0;
            }
            QToolButton:checked {
                background-color: black;
                color: white;
            }
        """)
        
        self.addToolBar(Qt.BottomToolBarArea, self.toolbar)
        
        # 创建工具栏动作
        self.camera_menu = QMenu("选择摄像头")
        self.camera_menu.setStyleSheet("""
            QMenu {
                background-color: #2c3e50;
                color: white;
                border: 1px solid #3498db;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 25px 6px 15px;
            }
            QMenu::item:selected {
                background-color: #3498db;
            }
        """)
        
        # 相机选择动作
        self.camera_action = QAction(QIcon("icons/switch_camera.png"), "切换摄像头", self)
        self.camera_action.setMenu(self.camera_menu)
        self.toolbar.addAction(self.camera_action)
        
        # 拍照按钮
        capture_action = QAction(QIcon("icons/capture.png"), "拍照", self)
        capture_action.triggered.connect(self.capture_image)
        capture_action.setShortcut(QKeySequence("Space"))
        self.toolbar.addAction(capture_action)
        
        # 保存按钮
        save_action = QAction(QIcon("icons/save.png"), "保存", self)
        save_action.triggered.connect(self.save_image)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        self.toolbar.addAction(save_action)
        
        self.toolbar.addSeparator()
        
        # 画笔按钮
        pen_action = QAction(QIcon("icons/pen.png"), "画笔", self)
        pen_action.triggered.connect(lambda: self.set_tool("pen"))
        pen_action.setShortcut(QKeySequence("P"))
        pen_action.setCheckable(True)
        pen_action.setChecked(True)
        self.toolbar.addAction(pen_action)
        
        # 移动/缩放按钮
        move_action = QAction(QIcon("icons/move.png"), "移动", self)
        move_action.triggered.connect(lambda: self.set_tool("move"))
        move_action.setShortcut(QKeySequence("M"))
        move_action.setCheckable(True)
        self.toolbar.addAction(move_action)
        
        # 橡皮擦按钮
        eraser_action = QAction(QIcon("icons/eraser.png"), "橡皮擦", self)
        eraser_action.triggered.connect(lambda: self.set_tool("eraser"))
        eraser_action.setShortcut(QKeySequence("E"))
        eraser_action.setCheckable(True)
        self.toolbar.addAction(eraser_action)
        
        # 清除按钮
        clear_action = QAction(QIcon("icons/clear.png"), "清除", self)
        clear_action.triggered.connect(self.clear_annotations)
        clear_action.setShortcut(QKeySequence("Ctrl+D"))
        self.toolbar.addAction(clear_action)
        
        # 撤回按钮
        undo_action = QAction(QIcon("icons/undo.png"), "撤回", self)
        undo_action.triggered.connect(self.undo_annotation)
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        self.toolbar.addAction(undo_action)
        
        self.toolbar.addSeparator()
        
        # 画笔设置按钮
        pen_settings_action = QAction(QIcon("icons/settings.png"), "画笔设置", self)
        pen_settings_action.triggered.connect(self.open_pen_settings)
        pen_settings_action.setShortcut(QKeySequence("Ctrl+P"))
        self.toolbar.addAction(pen_settings_action)
        
        # 照片面板按钮
        photos_action = QAction(QIcon("icons/photos.png"), "照片", self)
        photos_action.triggered.connect(self.toggle_photo_dock)
        self.toolbar.addAction(photos_action)
        
        # 添加最小化按钮
        minimize_action = QAction(QIcon("icons/minimize.png"), "最小化", self)
        minimize_action.triggered.connect(self.showMinimized)
        minimize_action.setShortcut(QKeySequence("Ctrl+M"))
        self.toolbar.addAction(minimize_action)
        
        # 创建折叠菜单栏
        self.foldable_menu = QToolBar("更多选项")
        self.foldable_menu.setIconSize(QSize(24, 24))
        self.foldable_menu.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.foldable_menu.setStyleSheet("""
            QToolBar {
                background-color: #2c3e50;
                border-top: 1px solid #3498db;
                padding: 4px;
                spacing: 6px;
            }
            QToolButton {
                background-color: white;
                color: #2c3e50;
                border-radius: 4px;
                padding: 4px;
                font-size: 10px;
                min-width: 40px;
                min-height: 40px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
            QToolButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        
        # 创建折叠菜单按钮
        self.fold_button = QPushButton()
        self.fold_button.setIcon(QIcon("icons/more.png"))
        self.fold_button.setText("更多")
        self.fold_button.setFixedHeight(40)
        self.fold_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
                padding: 4px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.fold_button.clicked.connect(self.toggle_foldable_menu)
        self.toolbar.addWidget(self.fold_button)
        
        # 添加折叠菜单栏到主窗口
        self.addToolBar(Qt.BottomToolBarArea, self.foldable_menu)
        self.foldable_menu.hide()  # 初始隐藏
        
        # 添加菜单项到折叠菜单
        # 导入按钮
        import_action = QAction(QIcon("icons/import.png"), "导入照片", self)
        import_action.triggered.connect(self.import_image)
        self.foldable_menu.addAction(import_action)
        
        # 梯形校正按钮
        perspective_action = QAction(QIcon("icons/correction.png"), "梯形校正", self)
        perspective_action.triggered.connect(self.open_perspective_correction)
        self.foldable_menu.addAction(perspective_action)
        
        # 画面调节按钮
        adjustment_action = QAction(QIcon("icons/adjust.png"), "画面调节", self)
        adjustment_action.triggered.connect(self.open_image_adjustment)
        self.foldable_menu.addAction(adjustment_action)
        
        # 退出按钮
        exit_action = QAction(QIcon("icons/exit.png"), "退出", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut(QKeySequence("Esc"))
        self.foldable_menu.addAction(exit_action)
        
        # 添加状态栏
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #2c3e50;
                color: white;
                font-size: 11px;
                border-top: 1px solid #3498db;
                padding: 3px;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("正在启动...")
        
        # 创建照片面板（右侧停靠）
        self.create_photo_dock()
        
        # 创建定时器用于更新视频
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        
        # 缩放指示器
        self.zoom_indicator = QLabel(self)
        self.zoom_indicator.setAlignment(Qt.AlignCenter)
        self.zoom_indicator.setStyleSheet("""
            QLabel {
                background-color: rgba(40, 40, 40, 180);
                color: white;
                font-size: 14px;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        self.zoom_indicator.hide()
        self.zoom_indicator_timer = QTimer(self)
        self.zoom_indicator_timer.setSingleShot(True)
        self.zoom_indicator_timer.timeout.connect(self.zoom_indicator.hide)
    
    def toggle_foldable_menu(self):
        """切换折叠菜单的可见性"""
        if self.foldable_menu.isVisible():
            self.foldable_menu.hide()
            self.fold_button.setIcon(QIcon("icons/more.png"))
            self.fold_button.setText("更多")
        else:
            self.foldable_menu.show()
            self.fold_button.setIcon(QIcon("icons/less.png"))
            self.fold_button.setText("收起")
    
    def create_photo_dock(self):
        """创建照片停靠面板"""
        self.photo_dock = QDockWidget("照片库", self)
        self.photo_dock.setObjectName("PhotoDock")
        self.photo_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.photo_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.photo_dock.setMinimumWidth(250)
        self.addDockWidget(Qt.RightDockWidgetArea, self.photo_dock)
        
        # 创建主部件
        dock_widget = QWidget()
        self.photo_dock.setWidget(dock_widget)
        
        # 主布局
        layout = QVBoxLayout(dock_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 标题栏
        title_layout = QHBoxLayout()
        
        # 标题
        title_label = QLabel("捕获的照片")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                padding: 3px;
            }
        """)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_layout.addWidget(title_label)
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 12px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        close_btn.clicked.connect(self.photo_dock.hide)
        title_layout.addWidget(close_btn)
        
        layout.addLayout(title_layout)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
                border: 1px solid #444444;
                border-radius: 6px;
            }
            QScrollBar:vertical {
                background: #2c3e50;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #3498db;
                min-height: 25px;
                border-radius: 6px;
            }
        """)
        
        # 捕获图像列表容器
        self.captured_list_widget = QListWidget()
        self.captured_list_widget.setViewMode(QListWidget.IconMode)
        self.captured_list_widget.setIconSize(QSize(120, 90))
        self.captured_list_widget.setResizeMode(QListWidget.Adjust)
        self.captured_list_widget.setSpacing(8)
        self.captured_list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                padding: 8px;
            }
            QListWidget::item {
                border: 1px solid #444444;
                border-radius: 6px;
                background-color: #2c3e50;
                padding: 4px;
            }
            QListWidget::item:selected {
                border: 2px solid #3498db;
            }
        """)
        self.captured_list_widget.itemClicked.connect(self.select_captured_image)
        
        scroll_area.setWidget(self.captured_list_widget)
        layout.addWidget(scroll_area, 1)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setFixedHeight(30)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        clear_btn.clicked.connect(self.clear_captured_images)
        btn_layout.addWidget(clear_btn)
        
        # 返回直播按钮
        back_to_live_btn = QPushButton("返回直播")
        back_to_live_btn.setFixedHeight(30)
        back_to_live_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        back_to_live_btn.clicked.connect(self.back_to_live)
        btn_layout.addWidget(back_to_live_btn)
        
        layout.addLayout(btn_layout)
        
        # 初始隐藏
        self.photo_dock.hide()
    
    def toggle_photo_dock(self):
        """切换照片面板的可见性"""
        if self.photo_dock.isVisible():
            self.photo_dock.hide()
        else:
            self.update_photo_dock()
            self.photo_dock.show()
    
    def show_startup_image(self):
        """显示启动图像"""
        try:
            # 尝试加载启动图像
            startup_pixmap = QPixmap("boot.JPG")
            if not startup_pixmap.isNull():
                screen_size = QApplication.primaryScreen().size()
                scaled_pixmap = startup_pixmap.scaled(
                    screen_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.video_label.setPixmap(scaled_pixmap)
                self.video_label.setAlignment(Qt.AlignCenter)
                self.startup_image = startup_pixmap
                self.showing_startup = True
                self.status_bar.showMessage("正在启动...")
                return
        except Exception as e:
            print(f"加载启动图错误: {e}")
        
        # 如果加载失败，显示黑色背景
        self.video_label.setPixmap(QPixmap())
        self.video_label.setStyleSheet("background-color: black;")
        self.startup_image = None
    
    def open_pen_settings(self):
        """打开画笔设置对话框"""
        dialog = ColorWidthDialog(self, self.pen_color, self.pen_width)
        if dialog.exec_() == QDialog.Accepted:
            self.pen_color, self.pen_width = dialog.get_settings()
            self.status_bar.showMessage(f"画笔设置已更新 - 颜色: {self.pen_color.name()}, 粗细: {self.pen_width}px")
    
    def open_perspective_correction(self):
        """打开梯形校正对话框（使用当前视频帧作为背景）"""
        # 检查摄像头是否激活
        if not self.camera_active or self.current_frame is None:
            QMessageBox.warning(self, "警告", "请先连接摄像头并确保有视频帧")
            return
        
        # 获取当前帧的分辨率
        try:
            resolution = (self.current_frame.shape[1], self.current_frame.shape[0])
        except Exception as e:
            QMessageBox.warning(self, "错误", f"获取分辨率失败: {e}")
            return
        
        # 如果有保存的校正点，使用归一化坐标
        saved_points = []
        if self.perspective_points and len(self.perspective_points) == 4:
            saved_points = [
                QPointF(p.x() / resolution[0], p.y() / resolution[1]) for p in self.perspective_points
            ]
        
        # 使用当前视频帧作为背景
        if self.base_image:
            # 创建并显示梯形校正对话框
            dialog = PerspectiveCorrectionDialog(
                self, 
                saved_points, 
                self.base_image.copy(),
                resolution
            )
            if dialog.exec_() == QDialog.Accepted:
                self.perspective_points = dialog.get_points()
                self.status_bar.showMessage("梯形校正已应用")
                self.save_config()
    
    def open_image_adjustment(self):
        """打开画面调节对话框"""
        dialog = ImageAdjustmentDialog(
            self,
            self.image_adjustments["brightness"],
            self.image_adjustments["contrast"],
            self.image_adjustments["orientation"],
            self.image_adjustments["flip_horizontal"]
        )
        
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            self.image_adjustments = settings
            self.status_bar.showMessage("画面调节设置已应用")
            self.save_config()
    
    def import_image(self):
        """导入照片文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片文件", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.tif);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
            
        # 加载图片
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            QMessageBox.warning(self, "错误", "无法加载图片文件")
            return
        
        # 创建捕获图像对象
        captured = CapturedImage(pixmap)
        captured.timestamp = f"导入: {os.path.basename(file_path)}"
        self.captured_images.append(captured)
        
        # 停止摄像头
        if self.camera_active:
            self.stop_camera()
        
        # 显示导入的图片
        self.select_captured_image_index(len(self.captured_images) - 1)
        
        # 更新照片面板
        if self.photo_dock:
            self.update_photo_dock()
            self.photo_dock.show()
        
        self.status_bar.showMessage(f"已导入图片: {os.path.basename(file_path)}")
    
    def select_captured_image_index(self, index):
        """选择指定索引的捕获图像"""
        if 0 <= index < len(self.captured_images):
            self.current_captured_image = self.captured_images[index]
            
            # 停止摄像头
            if self.camera_active:
                self.stop_camera()
            
            # 显示捕获的图像
            pixmap = self.current_captured_image.get_annotated_pixmap()
            self.video_label.setPixmap(pixmap.scaled(
                self.video_label.width(), 
                self.video_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
            self.status_bar.showMessage(f"正在查看: {self.current_captured_image.timestamp}")
    
    def switch_camera(self, index):
        """切换到指定摄像头"""
        if self.camera_active:
            self.stop_camera()
            
        # 显示加载状态
        self.status_bar.showMessage(f"正在连接摄像头 {index}...")
        QApplication.processEvents()
        
        # 使用线程初始化摄像头
        self.camera_thread = CameraInitThread(index)
        self.camera_thread.finished.connect(self.on_camera_connected)
        self.camera_thread.error.connect(self.on_camera_error)
        self.camera_thread.start()
    
    def on_camera_connected(self, cap):
        """摄像头连接成功"""
        self.cap = cap
        self.camera_active = True
        self.current_camera_index = self.camera_thread.camera_index
        self.timer.start(int(1000 / self.target_fps))
        
        # 获取实际分辨率
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.camera_resolution = (width, height)
        
        # 获取摄像头名称
        camera_name = self.get_camera_name(self.current_camera_index)
        self.status_bar.showMessage(f"已连接: {camera_name} - {width}x{height} @ {self.target_fps}fps")
        self.save_config()
    
    def on_camera_error(self, error_msg):
        """摄像头连接错误"""
        self.status_bar.showMessage(error_msg)
    
    def get_camera_name(self, index):
        """获取摄像头型号名称"""
        if index in self.camera_names:
            return self.camera_names[index]
        
        # 在Windows上尝试获取摄像头名称
        camera_name = f"摄像头 {index}"
        if platform.system() == "Windows":
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                    r"SYSTEM\CurrentControlSet\Control\Class\{6BDD1FC6-810F-11D0-BEC7-08002BE2092F}")
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        device_name, _ = winreg.QueryValueEx(subkey, "DeviceName")
                        if device_name.startswith("@device:pnp"):
                            # 提取友好名称
                            friendly_name, _ = winreg.QueryValueEx(subkey, "FriendlyName")
                            if f"#{index}" in subkey_name:
                                camera_name = friendly_name
                                self.camera_names[index] = camera_name
                                break
                    except:
                        continue
            except:
                pass
        
        return camera_name
    
    def update_camera_menu(self):
        """更新摄像头菜单"""
        self.camera_menu.clear()
        
        # 检测可用摄像头
        self.camera_list = self.detect_cameras()
        
        if not self.camera_list:
            action = self.camera_menu.addAction("未检测到可用摄像头")
            action.setEnabled(False)
            return
        
        for i in self.camera_list:
            camera_name = self.get_camera_name(i)
            action = self.camera_menu.addAction(f"{camera_name} (摄像头 {i})")
            action.triggered.connect(lambda checked, idx=i: self.switch_camera(idx))
    
    def detect_cameras(self, max_check=5):
        """检测可用摄像头"""
        available_cameras = []
        
        for i in range(max_check):
            try:
                if platform.system() == "Windows":
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                else:
                    cap = cv2.VideoCapture(i)
                    
                if cap.isOpened():
                    available_cameras.append(i)
                    cap.release()
            except:
                pass
        
        return available_cameras
    
    def auto_connect_camera(self):
        """自动连接摄像头"""
        # 在后台线程中检测摄像头
        threading.Thread(target=self.auto_connect_camera_thread, daemon=True).start()
    
    def auto_connect_camera_thread(self):
        """自动连接摄像头的后台线程"""
        # 更新摄像头菜单
        self.camera_list = self.detect_cameras()
        self.update_camera_menu()
        
        # 首先尝试使用配置文件中保存的摄像头索引
        if self.current_camera_index >= 0 and self.current_camera_index in self.camera_list:
            self.switch_camera(self.current_camera_index)
            return
        
        # 尝试其他摄像头
        for i in self.camera_list:
            if i == self.current_camera_index:
                continue
                
            self.switch_camera(i)
            time.sleep(1)
            if self.camera_active:
                self.current_camera_index = i
                return
        
        # 如果没有找到摄像头
        self.status_bar.showMessage("未检测到可用摄像头")
        self.current_camera_index = -1
    
    def stop_camera(self):
        """停止摄像头"""
        if self.camera_active:
            self.timer.stop()
            if self.cap:
                self.cap.release()
            self.camera_active = False
            self.current_camera_index = -1
    
    def apply_image_adjustments(self, frame):
        """应用画面调节设置"""
        if frame is None:
            return frame
        
        # 应用亮度和对比度
        brightness = self.image_adjustments["brightness"] - 100  # -100 to 100
        contrast = self.image_adjustments["contrast"] / 100.0  # 0.0 to 2.0
        
        # 应用公式: output = alpha * input + beta
        alpha = contrast
        beta = brightness
        
        adjusted = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
        
        # 应用方向调整
        orientation = self.image_adjustments["orientation"]
        if orientation == 1:  # 90°
            adjusted = cv2.rotate(adjusted, cv2.ROTATE_90_CLOCKWISE)
        elif orientation == 2:  # 180°
            adjusted = cv2.rotate(adjusted, cv2.ROTATE_180)
        elif orientation == 3:  # 270°
            adjusted = cv2.rotate(adjusted, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # 应用镜像翻转
        if self.image_adjustments["flip_horizontal"]:
            adjusted = cv2.flip(adjusted, 1)
        
        return adjusted
    
    def update_frame(self):
        """更新视频帧"""
        if self.cap and self.cap.isOpened():    
            ret, frame = self.cap.read()
            if not ret:
                self.status_bar.showMessage("摄像头读取错误")
                return
            
            # 应用画面调节
            frame = self.apply_image_adjustments(frame)
            
            # 应用梯形校正
            if self.perspective_points and len(self.perspective_points) == 4:
                try:
                    h, w = frame.shape[:2]
                    src_points = np.array([
                        [0, 0], [w-1, 0], [w-1, h-1], [0, h-1]
                    ], dtype=np.float32)
                    
                    dst_points = np.array([
                        [self.perspective_points[0].x(), self.perspective_points[0].y()],
                        [self.perspective_points[1].x(), self.perspective_points[1].y()],
                        [self.perspective_points[2].x(), self.perspective_points[2].y()],
                        [self.perspective_points[3].x(), self.perspective_points[3].y()]
                    ], dtype=np.float32)
                    
                    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
                    frame = cv2.warpPerspective(frame, matrix, (w, h))
                except Exception as e:
                    print(f"梯形校正错误: {e}")
            
            # 存储原始背景帧
            self.background_frame = frame.copy()
            
            # 转换颜色空间 BGR -> RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            
            # 创建QImage
            image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.base_image = QPixmap.fromImage(image)
            self.current_frame = frame
        else:
            # 如果没有摄像头，使用黑色背景
            self.base_image = QPixmap(self.video_label.size())
            self.base_image.fill(Qt.black)
            self.current_frame = None
        
        # 更新显示
        self.update_display()
    
    def update_display(self):
        """更新显示（考虑批注、缩放和拖动）"""
        if not self.base_image:
            return
            
        # 创建基础图像副本
        display_pixmap = self.base_image.copy()
        
        # 如果有批注图层，将其绘制到基础图像上
        if self.annotation_layer and not self.annotation_layer.isNull():
            painter = QPainter(display_pixmap)
            painter.drawPixmap(0, 0, self.annotation_layer)
            painter.end()
        
        # 应用缩放和偏移
        scaled_pixmap = display_pixmap.scaled(
            int(display_pixmap.width() * self.zoom_factor),
            int(display_pixmap.height() * self.zoom_factor),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        # 创建最终的显示图像
        final_pixmap = QPixmap(self.video_label.size())
        final_pixmap.fill(Qt.black)
        
        painter = QPainter(final_pixmap)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # 计算绘制位置（居中）
        x = (self.video_label.width() - scaled_pixmap.width()) // 2 + int(self.zoom_offset.x())
        y = (self.video_label.height() - scaled_pixmap.height()) // 2 + int(self.zoom_offset.y())
        
        # 绘制缩放后的图像
        painter.drawPixmap(x, y, scaled_pixmap)
        painter.end()
        
        self.video_label.setPixmap(final_pixmap)
    
    def capture_image(self):
        """捕获当前画面"""
        # 即使没有摄像头，也可以捕获当前显示的内容
        current_pixmap = self.video_label.pixmap()
        if not current_pixmap or current_pixmap.isNull():
            blank_image = QImage(640, 480, QImage.Format_RGB888)
            blank_image.fill(Qt.black)
            current_pixmap = QPixmap.fromImage(blank_image)
        
        # 创建捕获图像对象
        captured = CapturedImage(current_pixmap)
        self.captured_images.append(captured)
        
        # 更新照片面板
        if self.photo_dock and self.photo_dock.isVisible():
            self.update_photo_dock()
        
        self.status_bar.showMessage(f"已捕获图像 - {captured.timestamp}")
    
    def update_photo_dock(self):
        """更新照片面板内容"""
        if not self.photo_dock:
            return
        
        self.captured_list_widget.clear()
        
        for i, captured in enumerate(self.captured_images):
            item = QListWidgetItem()
            item.setIcon(QIcon(captured.thumbnail))
            item.setText(captured.timestamp)
            item.setData(Qt.UserRole, i)
            self.captured_list_widget.addItem(item)
    
    def select_captured_image(self, item):
        """选择捕获的图像"""
        index = item.data(Qt.UserRole)
        self.select_captured_image_index(index)
    
    def back_to_live(self):
        """返回直播画面"""
        # 清除实时批注
        self.annotations = []
        self.zoom_factor = 1.0
        self.zoom_offset = QPointF(0, 0)
        self.current_captured_image = None
        self.annotation_layer = None
        
        # 重新连接摄像头
        if not self.camera_active and self.current_camera_index >= 0:
            self.switch_camera(self.current_camera_index)
        
        self.status_bar.showMessage("已返回实时画面")
    
    def clear_captured_images(self):
        """清空所有捕获的图像"""
        if not self.captured_images:
            return
            
        reply = QMessageBox.question(self, "确认清空", 
                                    "确定要清空所有捕获的照片吗？",
                                    QMessageBox.Yes | QMessageBox.No, 
                                    QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.captured_images = []
            self.captured_list_widget.clear()
            self.current_captured_image = None
            self.status_bar.showMessage("已清空所有捕获的照片")
    
    def eventFilter(self, source, event):
        """事件过滤器处理触控和鼠标事件"""
        if source == self.video_label:
            # 处理触控事件
            if event.type() == QEvent.TouchBegin:
                self.handle_touch_begin(event)
                return True
            elif event.type() == QEvent.TouchUpdate:
                self.handle_touch_update(event)
                return True
            elif event.type() == QEvent.TouchEnd:
                self.handle_touch_end(event)
                return True
            
            # 处理鼠标事件
            elif event.type() == QEvent.MouseButtonPress:
                self.handle_mouse_press(event)
                return True
            elif event.type() == QEvent.MouseMove:
                self.handle_mouse_move(event)
                return True
            elif event.type() == QEvent.MouseButtonRelease:
                self.handle_mouse_release(event)
                return True
            elif event.type() == QEvent.Wheel:
                self.handle_wheel_event(event)
                return True
        
        return super().eventFilter(source, event)
    
    def handle_touch_begin(self, event):
        """处理触控开始事件"""
        self.last_touch_points = {}
        touch_area = 0.0
        
        for touch_point in event.touchPoints():
            self.last_touch_points[touch_point.id()] = touch_point.pos()
            
            # 计算触控面积
            size = touch_point.ellipseDiameters()
            if not size.isNull():
                a = size.width() / 2
                b = size.height() / 2
                area = math.pi * a * b
                touch_area += area
        
        # 检测手掌触控
        if touch_area > self.palm_threshold:
            if self.current_tool != "eraser":
                self.previous_tool = self.current_tool
                self.current_tool = "eraser"
                self.status_bar.showMessage("触控面积较大，已自动切换为橡皮擦模式")
        
        # 移动模式：单指拖动
        if self.current_tool == "move" and len(self.last_touch_points) == 1:
            self.dragging = True
            self.drag_start_pos = list(self.last_touch_points.values())[0]
            return True
        
        # 绘制模式：单指绘制
        elif len(self.last_touch_points) == 1:
            self.touch_drawing = True
            pos = list(self.last_touch_points.values())[0]
            self.start_drawing(pos)
            return True
    
    def handle_touch_update(self, event):
        """处理触控更新事件"""
        current_time = time.time()
        touch_points = {}
        
        for touch_point in event.touchPoints():
            touch_points[touch_point.id()] = touch_point.pos()
        
        # 移动模式：单指拖动
        if self.current_tool == "move" and self.dragging and len(touch_points) == 1:
            current_pos = list(touch_points.values())[0]
            delta = current_pos - self.drag_start_pos
            self.zoom_offset += delta
            self.drag_start_pos = current_pos
            self.update_display()
            return True
        
        # 移动模式：双指缩放
        elif self.current_tool == "move" and len(touch_points) == 2:
            ids = list(touch_points.keys())
            p1_prev = self.last_touch_points.get(ids[0])
            p2_prev = self.last_touch_points.get(ids[1])
            p1_curr = touch_points[ids[0]]
            p2_curr = touch_points[ids[1]]
            
            if p1_prev and p2_prev:
                # 计算缩放比例
                prev_distance = (p1_prev - p2_prev).manhattanLength()
                curr_distance = (p1_curr - p2_curr).manhattanLength()
                scale_factor = curr_distance / prev_distance if prev_distance > 0 else 1.0
                self.zoom_factor *= scale_factor
                self.zoom_factor = max(0.5, min(self.zoom_factor, 3.0))
                
                # 计算平移
                center_prev = (p1_prev + p2_prev) / 2
                center_curr = (p1_curr + p2_curr) / 2
                self.zoom_offset += center_curr - center_prev
                
                # 显示缩放指示器
                self.show_zoom_indicator()
                self.update_display()
            return True
        
        # 绘制模式：双指手势识别
        elif len(touch_points) == 2:
            self.touch_drawing = False
            ids = list(touch_points.keys())
            p1_prev = self.last_touch_points.get(ids[0])
            p2_prev = self.last_touch_points.get(ids[1])
            p1_curr = touch_points[ids[0]]
            p2_curr = touch_points[ids[1]]
            
            if p1_prev and p2_prev:
                # 计算缩放比例
                prev_distance = (p1_prev - p2_prev).manhattanLength()
                curr_distance = (p1_curr - p2_curr).manhattanLength()
                scale_factor = curr_distance / prev_distance if prev_distance > 0 else 1.0
                self.zoom_factor *= scale_factor
                self.zoom_factor = max(0.5, min(self.zoom_factor, 3.0))
                
                # 计算平移
                center_prev = (p1_prev + p2_prev) / 2
                center_curr = (p1_curr + p2_curr) / 2
                self.zoom_offset += center_curr - center_prev
                
                # 显示缩放指示器
                self.show_zoom_indicator()
        # 绘制模式：单指触控 - 继续绘制
        elif self.touch_drawing and len(touch_points) == 1:
            if current_time - self.last_draw_time < 0.02:
                return True
            pos = list(touch_points.values())[0]
            self.continue_drawing(pos)
            self.last_draw_time = current_time
        
        self.last_touch_points = touch_points
        self.update_display()
        return True
    
    def handle_touch_end(self, event):
        """处理触控结束事件"""
        # 移动模式：结束拖动
        if self.current_tool == "move":
            self.dragging = False
        
        # 绘制模式：结束绘制
        self.touch_drawing = False
        self.last_touch_points = {}
        self.finalize_drawing()
        
        # 恢复原工具
        if hasattr(self, 'previous_tool') and self.current_tool == "eraser":
            self.current_tool = self.previous_tool
            self.status_bar.showMessage(f"已恢复为 {self.current_tool} 模式")
        
        return True
    
    def handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        # 移动模式：开始拖动
        if self.current_tool == "move":
            self.dragging = True
            self.drag_start_pos = event.pos()
            return True
        
        # 绘制模式：开始绘制
        self.start_drawing(event.pos())
        return True
    
    def handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        current_time = time.time()
        
        # 移动模式：拖动
        if self.current_tool == "move" and self.dragging:
            current_pos = event.pos()
            delta = current_pos - self.drag_start_pos
            self.zoom_offset += delta
            self.drag_start_pos = current_pos
            self.update_display()
            return True
        
        # 绘制模式：继续绘制
        if self.drawing:
            if current_time - self.last_draw_time < 0.02:
                return True
            self.continue_drawing(event.pos())
            self.last_draw_time = current_time
            return True
        
        return True
    
    def handle_mouse_release(self, event):
        """处理鼠标释放事件"""
        # 移动模式：结束拖动
        if self.current_tool == "move":
            self.dragging = False
        
        # 绘制模式：结束绘制
        self.finalize_drawing()
        return True
    
    def finalize_drawing(self):
        """完成绘制"""
        if self.temp_annotation:
            if self.current_captured_image:
                self.current_captured_image.add_annotation(self.temp_annotation)
            else:
                self.annotations.append(self.temp_annotation)
            
            self.temp_annotation = None
            self.update_display()
        
        self.drawing = False
        self.last_point = None
        self.current_annotation = None
        self.arrow_start_point = None
    
    def handle_wheel_event(self, event):
        """处理鼠标滚轮事件进行缩放"""
        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9
        
        # 获取鼠标位置（缩放中心）
        mouse_pos = event.pos()
        
        # 计算鼠标在图像上的位置（缩放前的坐标）
        old_img_pos = self.map_to_image(mouse_pos)
        if not old_img_pos:
            return
        
        # 应用缩放
        self.zoom_factor *= zoom_factor
        self.zoom_factor = max(0.5, min(self.zoom_factor, 3.0))
        
        # 计算缩放后同一鼠标位置对应的新图像位置
        new_img_pos = self.map_to_image(mouse_pos)
        if not new_img_pos:
            return
        
        # 调整偏移，使得鼠标下的图像位置保持不变
        self.zoom_offset += QPointF(
            (new_img_pos.x() - old_img_pos.x()) * self.zoom_factor,
            (new_img_pos.y() - old_img_pos.y()) * self.zoom_factor
        )
        
        self.update_display()
        self.show_zoom_indicator()
    
    def show_zoom_indicator(self):
        """显示缩放指示器"""
        zoom_percent = int(self.zoom_factor * 100)
        self.zoom_indicator.setText(f"缩放: {zoom_percent}%")
        self.zoom_indicator.adjustSize()
        
        # 位置在右上角
        x = self.video_label.width() - self.zoom_indicator.width() - 10
        y = 10
        
        self.zoom_indicator.move(x, y)
        self.zoom_indicator.show()
        
        # 3秒后隐藏
        self.zoom_indicator_timer.start(3000)
    
    def start_drawing(self, pos):
        """开始绘制批注"""
        if self.current_tool is None or self.current_tool == "move":
            return
        
        # 计算实际图像位置
        img_pos = self.map_to_image(pos)
        if not img_pos:
            return
        
        # 初始化批注图层
        if self.annotation_layer is None and self.base_image:
            self.annotation_layer = QPixmap(self.base_image.size())
            self.annotation_layer.fill(Qt.transparent)
        
        # 创建临时批注
        if self.current_tool == "eraser":
            self.temp_annotation = {
                "tool": self.current_tool,
                "points": [img_pos],
                "width": self.pen_width * 3  # 橡皮擦更宽
            }
        else:
            self.temp_annotation = {
                "tool": self.current_tool,
                "points": [img_pos],
                "color": self.pen_color,
                "width": self.pen_width
            }
        
        self.drawing = True
        self.last_point = img_pos
        self.draw_temp_annotation()
    
    def continue_drawing(self, pos):
        """继续绘制批注"""
        if not self.drawing or self.current_tool is None or not self.temp_annotation or self.current_tool == "move":
            return
        
        # 计算实际图像位置
        img_pos = self.map_to_image(pos)
        if not img_pos:
            return
        
        # 添加点到临时批注
        self.temp_annotation["points"].append(img_pos)
        
        # 立即绘制临时批注
        self.draw_temp_annotation()
    
    def draw_temp_annotation(self):
        """绘制临时批注到图层"""
        if not self.annotation_layer or not self.temp_annotation:
            return
            
        # 创建临时图层
        temp_layer = self.annotation_layer.copy()
        painter = QPainter(temp_layer)
        painter.setRenderHint(QPainter.Antialiasing)
        
        tool = self.temp_annotation["tool"]
        points = self.temp_annotation["points"]
        width = self.temp_annotation["width"]
        
        if tool == "eraser":
            if len(points) > 1:
                # 橡皮擦绘制背景色
                painter.setCompositionMode(QPainter.CompositionMode_Source)
                painter.setPen(QPen(Qt.transparent, width * 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                
                # 绘制路径
                path = QPainterPath()
                path.moveTo(points[0])
                for i in range(1, len(points)):
                    path.lineTo(points[i])
                painter.drawPath(path)
        else:
            # 正常绘制
            painter.setPen(QPen(self.temp_annotation["color"], width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            
            if len(points) > 1:
                # 绘制路径
                path = QPainterPath()
                path.moveTo(points[0])
                for i in range(1, len(points)):
                    path.lineTo(points[i])
                painter.drawPath(path)
        
        painter.end()
        
        # 更新显示
        self.annotation_layer = temp_layer
        self.update_display()
    
    def map_to_image(self, pos):
        """将屏幕坐标映射到图像坐标"""
        if not self.base_image or self.base_image.isNull():
            return None
            
        # 获取标签尺寸
        label_size = self.video_label.size()
        
        # 获取基础图像尺寸
        base_width = self.base_image.width()
        base_height = self.base_image.height()
        
        # 计算缩放后的图像尺寸
        scaled_width = base_width * self.zoom_factor
        scaled_height = base_height * self.zoom_factor
        
        # 计算图像在label中的实际显示区域
        x_offset = (label_size.width() - scaled_width) // 2 + int(self.zoom_offset.x())
        y_offset = (label_size.height() - scaled_height) // 2 + int(self.zoom_offset.y())
        
        # 转换为图像坐标
        img_x = (pos.x() - x_offset) / self.zoom_factor
        img_y = (pos.y() - y_offset) / self.zoom_factor
        
        # 检查是否在图像范围内
        if 0 <= img_x < base_width and 0 <= img_y < base_height:
            return QPoint(int(img_x), int(img_y))
        return None
    
    def set_tool(self, tool):
        """设置当前工具"""
        self.current_tool = tool
        self.status_bar.showMessage(f"已选择: {tool}")
        
        # 更新工具栏按钮状态
        for action in self.toolbar.actions():
            if action.text() in ["画笔", "移动", "橡皮擦"]:
                action.setChecked(action.text() == tool)
        
        # 更新鼠标光标
        if tool == "eraser":
            pixmap = QPixmap(28, 28)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(Qt.white, 2))
            painter.setBrush(Qt.white)
            painter.drawEllipse(0, 0, 28, 28)
            painter.end()
            self.setCursor(QCursor(pixmap))
        elif tool == "move":
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
    
    def clear_annotations(self):
        """清除所有批注"""
        if self.current_captured_image:
            self.current_captured_image.clear_annotations()
            pixmap = self.current_captured_image.get_annotated_pixmap()
            self.video_label.setPixmap(pixmap.scaled(
                self.video_label.width(), 
                self.video_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
            self.status_bar.showMessage("已清除当前图像的批注")
        else:
            self.annotations = []
            self.annotation_layer = None
            self.status_bar.showMessage("已清除实时画面的批注")
            self.update_display()
    
    def undo_annotation(self):
        """撤回最后一步批注"""
        if self.current_captured_image:
            if self.current_captured_image.undo_annotation():
                pixmap = self.current_captured_image.get_annotated_pixmap()
                self.video_label.setPixmap(pixmap.scaled(
                    self.video_label.width(), 
                    self.video_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                ))
                self.status_bar.showMessage("已撤回上一步操作")
                return True
        elif self.annotations:
            self.annotations.pop()
            # 重新绘制批注图层
            self.redraw_annotation_layer()
            self.status_bar.showMessage("已撤回上一步操作")
            return True
        
        self.status_bar.showMessage("没有可撤回的操作")
        return False
    
    def redraw_annotation_layer(self):
        """重新绘制批注图层"""
        if not self.base_image:
            return
            
        self.annotation_layer = QPixmap(self.base_image.size())
        self.annotation_layer.fill(Qt.transparent)
        
        if not self.annotations:
            return
            
        painter = QPainter(self.annotation_layer)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for annotation in self.annotations:
            tool = annotation["tool"]
            points = annotation["points"]
            width = annotation["width"]
            
            if tool == "eraser":
                if len(points) > 1:
                    # 橡皮擦绘制背景色
                    painter.setCompositionMode(QPainter.CompositionMode_Source)
                    painter.setPen(QPen(Qt.transparent, width * 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    
                    # 绘制路径
                    path = QPainterPath()
                    path.moveTo(points[0])
                    for i in range(1, len(points)):
                        path.lineTo(points[i])
                    painter.drawPath(path)
            else:
                # 正常绘制
                painter.setPen(QPen(annotation["color"], width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                
                if len(points) > 1:
                    # 绘制路径
                    path = QPainterPath()
                    path.moveTo(points[0])
                    for i in range(1, len(points)):
                        path.lineTo(points[i])
                    painter.drawPath(path)
        
        painter.end()
    
    def save_image(self):
        """保存当前图像（带批注）"""
        if self.current_captured_image:
            pixmap = self.current_captured_image.get_annotated_pixmap()
        elif self.base_image:
            # 创建合成图像
            result_pixmap = self.base_image.copy()
            
            if self.annotation_layer and not self.annotation_layer.isNull():
                painter = QPainter(result_pixmap)
                painter.drawPixmap(0, 0, self.annotation_layer)
                painter.end()
        else:
            pixmap = self.video_label.pixmap()
            if pixmap is None or pixmap.isNull():
                self.status_bar.showMessage("没有可保存的图像")
                return
            else:
                result_pixmap = pixmap.copy()
        
        # 生成默认文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"capture_{timestamp}.png"
        
        # 保存图像
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存图像", default_filename, 
            "PNG图像 (*.png);;JPEG图像 (*.jpg *.jpeg)"
        )
        
        if file_path:
            if file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
                result_pixmap.save(file_path, "JPEG", 90)
            else:
                result_pixmap.save(file_path, "PNG")
            
            self.saved_image_path = file_path
            self.status_bar.showMessage(f"图像已保存到: {file_path}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        reply = QMessageBox.question(
            self, "确认退出",
            "确定要退出程序吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            event.ignore()
            return
        
        self.save_config()
        self.stop_camera()
        
        if self.photo_dock:
            self.photo_dock.close()
        
        event.accept()

# 辅助类
class CapturedImage:
    """捕获的图像及其批注"""
    def __init__(self, pixmap):
        self.original_pixmap = pixmap.copy()
        self.annotations = []
        self.thumbnail = pixmap.scaled(120, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.timestamp = datetime.now().strftime("%H:%M:%S")
        self.annotated_pixmap = None
    
    def get_annotated_pixmap(self):
        """获取带批注的图像"""
        if self.annotated_pixmap is None:
            self.annotated_pixmap = self.apply_annotations(self.original_pixmap.copy())
        return self.annotated_pixmap
    
    def apply_annotations(self, pixmap):
        """应用批注到图像"""
        # 创建透明图层
        annotation_layer = QPixmap(pixmap.size())
        annotation_layer.fill(Qt.transparent)
        
        painter = QPainter(annotation_layer)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for annotation in self.annotations:
            tool = annotation["tool"]
            points = annotation["points"]
            width = annotation["width"]
            
            if tool == "eraser":
                if len(points) > 1:
                    # 橡皮擦绘制背景色
                    painter.setCompositionMode(QPainter.CompositionMode_Source)
                    painter.setPen(QPen(Qt.transparent, width * 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    
                    # 绘制路径
                    path = QPainterPath()
                    path.moveTo(points[0])
                    for i in range(1, len(points)):
                        path.lineTo(points[i])
                    painter.drawPath(path)
            else:
                # 正常绘制
                painter.setPen(QPen(annotation["color"], width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                
                if len(points) > 1:
                    # 绘制路径
                    path = QPainterPath()
                    path.moveTo(points[0])
                    for i in range(1, len(points)):
                        path.lineTo(points[i])
                    painter.drawPath(path)
        
        painter.end()
        
        # 将批注图层绘制到原始图像上
        result_painter = QPainter(pixmap)
        result_painter.drawPixmap(0, 0, annotation_layer)
        result_painter.end()
        
        return pixmap
    
    def add_annotation(self, annotation):
        """添加批注"""
        self.annotations.append(annotation)
        self.annotated_pixmap = None
        self.thumbnail = self.get_annotated_pixmap().scaled(120, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    
    def clear_annotations(self):
        """清除所有批注"""
        self.annotations = []
        self.annotated_pixmap = None
        self.thumbnail = self.original_pixmap.scaled(120, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    
    def undo_annotation(self):
        """撤回最后一步批注"""
        if self.annotations:
            self.annotations.pop()
            self.annotated_pixmap = None
            self.thumbnail = self.get_annotated_pixmap().scaled(120, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            return True
        return False

if __name__ == "__main__":
    # 设置环境变量以优化性能
    os.environ["QT_LOGGING_RULES"] = "*.debug=false"
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    # 创建并显示主窗口
    window = VideoAnnotationApp()
    window.show()
    
    sys.exit(app.exec_())
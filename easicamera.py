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
                            QSizeGrip, QComboBox, QMenu, QLineEdit)
from PySide2.QtGui import (QImage, QPixmap, QPainter, QPen, QColor, QFont, QIcon, 
                         QTransform, QKeySequence, QPalette, QBrush, QMouseEvent,
                         QPainterPath, QRegion, QCursor, QFontMetrics, QIntValidator)
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

class SplashScreen(QWidget):
    """启动图界面"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建标签显示启动图
        self.splash_label = QLabel(self)
        self.splash_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.splash_label)
        
        # 设置窗口大小
        self.resize(800, 600)
        
        # 加载启动图
        self.load_splash_image()
        
        # 设置窗口位置居中
        self.center_on_screen()
    
    def center_on_screen(self):
        """将窗口居中显示"""
        screen = QApplication.primaryScreen().geometry()
        window_rect = self.frameGeometry()
        window_rect.moveCenter(screen.center())
        self.move(window_rect.topLeft())
    
    def load_splash_image(self):
        """加载启动图并缩放适应屏幕"""
        try:
            splash_pixmap = QPixmap("boot.JPG")
            if not splash_pixmap.isNull():
                # 获取屏幕尺寸
                screen_size = QApplication.primaryScreen().size()
                max_width = screen_size.width() * 0.5  # 最大宽度为屏幕宽度的50%
                max_height = screen_size.height() * 0.5  # 最大高度为屏幕高度的50%
                
                # 按比例缩放
                scaled_pixmap = splash_pixmap.scaled(
                    max_width, max_height, 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                
                # 设置启动图
                self.splash_label.setPixmap(scaled_pixmap)
                
                # 调整窗口大小以适应图像
                self.resize(scaled_pixmap.size())
            else:
                # 创建默认启动图
                default_pixmap = QPixmap(800, 600)
                default_pixmap.fill(Qt.darkGray)
                painter = QPainter(default_pixmap)
                painter.setPen(Qt.white)
                painter.setFont(QFont("Arial", 24))
                painter.drawText(default_pixmap.rect(), Qt.AlignCenter, "希沃视频展台")
                painter.end()
                self.splash_label.setPixmap(default_pixmap)
        except Exception as e:
            print(f"加载启动图错误: {e}")
            # 创建错误启动图
            error_pixmap = QPixmap(800, 600)
            error_pixmap.fill(Qt.darkRed)
            painter = QPainter(error_pixmap)
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 18))
            painter.drawText(error_pixmap.rect(), Qt.AlignCenter, f"无法加载启动图\n{str(e)}")
            painter.end()
            self.splash_label.setPixmap(error_pixmap)

class CameraInitThread(QThread):
    """摄像头初始化线程"""
    finished = Signal(object)  # 修改为传递cap对象
    error = Signal(str)
    
    def __init__(self, camera_index, width=None, height=None, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.width = width
        self.height = height
    
    def run(self):
        try:
            # 尝试多种分辨率
            resolutions = [
                (self.width, self.height) if self.width and self.height else (1280, 720),
                (1280, 720), 
                (640, 480), 
                (320, 240)
            ]
            cap = None
            
            for res in resolutions:
                try:
                    if res[0] is None or res[1] is None:
                        continue
                        
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

class ColorWidthDialog(QDialog):
    """画笔设置对话框 - 修改为实时保存，添加预设颜色"""
    def __init__(self, parent=None, current_color=QColor(255, 0, 0), current_width=8):
        super().__init__(parent)
        self.setWindowTitle("画笔设置")
        self.setWindowIcon(QIcon("icons/pen.png"))
        self.setFixedSize(400, 400)  # 增大尺寸以容纳预设颜色
        
        self.parent = parent  # 保存父窗口引用
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # 颜色选择部分
        color_group = QGroupBox("颜色")
        color_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        color_layout = QVBoxLayout()
        color_layout.setContentsMargins(10, 15, 10, 15)
        
        # 预设颜色网格
        preset_layout = QGridLayout()
        preset_layout.setSpacing(10)
        
        # 常用颜色列表
        self.preset_colors = [
            QColor(255, 0, 0),    # 红色
            QColor(0, 0, 255),    # 蓝色
            QColor(0, 255, 0),    # 绿色
            QColor(255, 255, 0),  # 黄色
            QColor(255, 0, 255),  # 紫色
            QColor(0, 255, 255),  # 青色
            QColor(255, 165, 0),  # 橙色
            QColor(128, 0, 128),  # 深紫
            QColor(0, 0, 0),      # 黑色
        ]
        
        # 创建颜色按钮
        self.color_buttons = []
        for i, color in enumerate(self.preset_colors):
            btn = QPushButton()
            btn.setFixedSize(40, 40)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color.name()};
                    border-radius: 20px;
                    border: 2px solid #cccccc;
                }}
                QPushButton:hover {{
                    border: 2px solid #3498db;
                }}
            """)
            btn.clicked.connect(lambda checked, c=color: self.select_preset_color(c))
            preset_layout.addWidget(btn, i // 3, i % 3)
            self.color_buttons.append(btn)
        
        color_layout.addLayout(preset_layout)
        
        # 其他颜色按钮
        other_color_btn = QPushButton("其他颜色...")
        other_color_btn.setFixedHeight(40)
        other_color_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        other_color_btn.clicked.connect(self.select_custom_color)
        color_layout.addWidget(other_color_btn)
        
        # 当前颜色显示
        self.color_display = QLabel()
        self.color_display.setFixedHeight(40)
        self.color_display.setAlignment(Qt.AlignCenter)
        self.set_color_display(current_color)
        color_layout.addWidget(self.color_display)
        
        color_group.setLayout(color_layout)
        layout.addWidget(color_group)
        
        # 画笔粗细部分
        width_group = QGroupBox("画笔粗细")
        width_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        width_layout = QVBoxLayout()
        width_layout.setContentsMargins(10, 15, 10, 10)
        
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(3, 20)
        self.width_slider.setValue(current_width)
        self.width_slider.valueChanged.connect(self.width_changed)
        self.width_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: #e0e0e0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                width: 20px;
                background: #3498db;
                border-radius: 10px;
                margin: -6px 0;
            }
            QSlider::sub-page:horizontal {
                background: #3498db;
                border-radius: 4px;
            }
        """)
        width_layout.addWidget(self.width_slider)
        
        self.width_label = QLabel(f"当前粗细: {current_width}px")
        self.width_label.setAlignment(Qt.AlignCenter)
        self.width_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        width_layout.addWidget(self.width_label)
        
        width_group.setLayout(width_layout)
        layout.addWidget(width_group)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(40)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
        
        # 存储当前设置
        self.selected_color = current_color
        self.selected_width = current_width
    
    def set_color_display(self, color):
        """设置颜色显示"""
        self.selected_color = color
        self.color_display.setStyleSheet(f"""
            QLabel {{
                background-color: {color.name()};
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                padding: 5px;
            }}
        """)
        self.color_display.setText(color.name())
        
        # 实时更新父窗口设置
        if self.parent:
            self.parent.pen_color = color
            self.parent.pen_width = self.selected_width
    
    def select_preset_color(self, color):
        """选择预设颜色"""
        self.set_color_display(color)
    
    def select_custom_color(self):
        """选择自定义颜色"""
        color = QColorDialog.getColor(self.selected_color, self)
        if color.isValid():
            self.set_color_display(color)
    
    def width_changed(self, width):
        """宽度改变事件"""
        self.selected_width = width
        self.width_label.setText(f"当前粗细: {width}px")
        
        # 实时更新父窗口设置
        if self.parent:
            self.parent.pen_width = width
            self.parent.pen_color = self.selected_color

class PerspectiveCorrectionDialog(QDialog):
    """梯形校正对话框 - 修复点显示问题"""
    def __init__(self, parent=None, image_size=(640, 480)):
        super().__init__(parent)
        self.setWindowTitle("梯形校正")
        self.setWindowIcon(QIcon("icons/correction.png"))
        self.setFixedSize(900, 700)
        
        self.image_size = image_size
        # 初始点位置改为基于图像大小的百分比
        self.correction_points = [
            QPoint(int(image_size[0]*0.1), int(image_size[1]*0.1)),  # 左上
            QPoint(int(image_size[0]*0.9), int(image_size[1]*0.1)),  # 右上
            QPoint(int(image_size[0]*0.9), int(image_size[1]*0.9)),  # 右下
            QPoint(int(image_size[0]*0.1), int(image_size[1]*0.9))   # 左下
        ]
        self.active_point = -1
        self.correction_matrix = None
        self.dragging = False
        
        # 创建主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # 说明标签
        info_label = QLabel("拖动四个角点进行梯形校正，点1:左上, 点2:右上, 点3:右下, 点4:左下")
        info_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #3498db;")
        layout.addWidget(info_label)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumSize(700, 500)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                background: #2c3e50;
                width: 14px;
                margin: 0px 0px 0px 0px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical {
                background: #3498db;
                min-height: 30px;
                border-radius: 7px;
            }
        """)
        
        # 图像显示区域
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(image_size[0] + 100, image_size[1] + 100)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border: 2px solid #3498db;
                border-radius: 8px;
            }
        """)
        self.image_label.mousePressEvent = self.handle_mouse_press
        self.image_label.mouseMoveEvent = self.handle_mouse_move
        self.image_label.mouseReleaseEvent = self.handle_mouse_release
        
        scroll_area.setWidget(self.image_label)
        layout.addWidget(scroll_area)
        
        # 控制区域
        control_layout = QHBoxLayout()
        control_layout.setSpacing(15)
        
        # 重置按钮
        reset_btn = QPushButton("重置校正点")
        reset_btn.setFixedHeight(40)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
        """)
        reset_btn.clicked.connect(self.reset_points)
        control_layout.addWidget(reset_btn)
        
        # 应用按钮
        apply_btn = QPushButton("应用校正")
        apply_btn.setFixedHeight(40)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        apply_btn.clicked.connect(self.accept)
        control_layout.addWidget(apply_btn)
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        control_layout.addWidget(cancel_btn)
        
        # 添加到主布局
        layout.addLayout(control_layout)
        self.setLayout(layout)
    
    def set_image(self, pixmap):
        """设置图像并绘制校正点"""
        self.original_pixmap = pixmap.copy()
        self.update_display()
    
    def update_display(self):
        """更新显示（绘制校正点） - 确保所有点可见"""
        if self.original_pixmap is None:
            return
            
        pixmap = self.original_pixmap.copy()
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制校正点
        point_colors = [QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255), QColor(255, 255, 0)]
        point_names = ["左上", "右上", "右下", "左下"]
        
        for i, point in enumerate(self.correction_points):
            # 确保点在图像范围内
            if point.x() < 0: point.setX(0)
            if point.y() < 0: point.setY(0)
            if point.x() >= pixmap.width(): point.setX(pixmap.width()-1)
            if point.y() >= pixmap.height(): point.setY(pixmap.height()-1)
            
            pen = QPen(point_colors[i])
            pen.setWidth(3)
            painter.setPen(pen)
            painter.setBrush(QBrush(point_colors[i]))
            painter.drawEllipse(point, 10, 10)
            
            # 绘制点编号和名称
            painter.setPen(QPen(Qt.white))
            painter.setFont(QFont("Arial", 12, QFont.Bold))
            painter.drawText(point.x() - 15, point.y() - 20, f"{i+1}:{point_names[i]}")
        
        # 绘制连接线
        pen = QPen(QColor(255, 165, 0))  # 橙色
        pen.setWidth(2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        
        for i in range(4):
            painter.drawLine(self.correction_points[i], self.correction_points[(i+1)%4])
        
        painter.end()
        
        # 显示图像
        self.image_label.setPixmap(pixmap)
        self.image_label.adjustSize()
    
    def handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        pos = event.pos()
        
        # 获取图像在label中的实际位置
        pixmap = self.image_label.pixmap()
        if pixmap is None:
            return
            
        label_size = self.image_label.size()
        pixmap_size = pixmap.size()
        x_offset = (label_size.width() - pixmap_size.width()) // 2
        y_offset = (label_size.height() - pixmap_size.height()) // 2
        
        # 转换为图像坐标
        img_pos = QPoint(pos.x() - x_offset, pos.y() - y_offset)
        
        # 检查是否点击了校正点
        for i, point in enumerate(self.correction_points):
            if (point - img_pos).manhattanLength() < 15:
                self.active_point = i
                self.dragging = True
                return
    
    def handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        if self.dragging and self.active_point >= 0:
            pos = event.pos()
            
            # 获取图像在label中的实际位置
            pixmap = self.image_label.pixmap()
            if pixmap is None:
                return
                
            label_size = self.image_label.size()
            pixmap_size = pixmap.size()
            x_offset = (label_size.width() - pixmap_size.width()) // 2
            y_offset = (label_size.height() - pixmap_size.height()) // 2
            
            # 转换为图像坐标
            img_pos = QPoint(pos.x() - x_offset, pos.y() - y_offset)
            
            # 更新点位置
            self.correction_points[self.active_point] = img_pos
            self.update_display()
    
    def handle_mouse_release(self, event):
        """处理鼠标释放事件"""
        self.active_point = -1
        self.dragging = False
    
    def reset_points(self):
        """重置校正点到默认位置"""
        self.correction_points = [
            QPoint(int(self.image_size[0]*0.1), int(self.image_size[1]*0.1)),  # 左上
            QPoint(int(self.image_size[0]*0.9), int(self.image_size[1]*0.1)),  # 右上
            QPoint(int(self.image_size[0]*0.9), int(self.image_size[1]*0.9)),  # 右下
            QPoint(int(self.image_size[0]*0.1), int(self.image_size[1]*0.9))   # 左下
        ]
        self.update_display()
    
    def get_correction_points(self):
        """获取校正点坐标"""
        return [
            (self.correction_points[0].x(), self.correction_points[0].y()),
            (self.correction_points[1].x(), self.correction_points[1].y()),
            (self.correction_points[2].x(), self.correction_points[2].y()),
            (self.correction_points[3].x(), self.correction_points[3].y())
    ]
    
    def set_correction_points(self, points):
        """设置校正点坐标"""
        if points and len(points) == 4:
            self.correction_points = [
                QPoint(points[0][0], points[0][1]),
                QPoint(points[1][0], points[1][1]),
                QPoint(points[2][0], points[2][1]),
                QPoint(points[3][0], points[3][1])
            ]
    
    def get_correction_matrix(self, size):
        """获取校正矩阵"""
        # 源点（校正点）
        src_points = np.array([
            [self.correction_points[0].x(), self.correction_points[0].y()],
            [self.correction_points[1].x(), self.correction_points[1].y()],
            [self.correction_points[2].x(), self.correction_points[2].y()],
            [self.correction_points[3].x(), self.correction_points[3].y()]
        ], dtype=np.float32)
        
        # 目标点（图像边界）
        dst_points = np.array([
            [0, 0],
            [size[0]-1, 0],
            [size[0]-1, size[1]-1],
            [0, size[1]-1]
        ], dtype=np.float32)
        
        # 计算透视变换矩阵
        matrix = cv2.getPerspectiveTransform(src_points, dst_points)
        return matrix

class ImageAdjustDialog(QDialog):
    """图像调整对话框 - 增强亮度效果并添加分辨率设置"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("画面调节")
        self.setWindowIcon(QIcon("icons/adjust.png"))
        self.setFixedSize(450, 450)  # 增加高度以容纳分辨率设置
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # 亮度调整
        brightness_group = QGroupBox("亮度/对比度调整")
        brightness_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        brightness_layout = QVBoxLayout()
        brightness_layout.setContentsMargins(10, 15, 10, 10)
        
        # 亮度滑块
        brightness_label = QLabel("亮度:")
        brightness_label.setStyleSheet("font-size: 14px;")
        brightness_layout.addWidget(brightness_label)
        
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: #e0e0e0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                width: 20px;
                background: #3498db;
                border-radius: 10px;
                margin: -6px 0;
            }
            QSlider::sub-page:horizontal {
                background: #3498db;
                border-radius: 4px;
            }
        """)
        brightness_layout.addWidget(self.brightness_slider)
        
        self.brightness_value = QLabel("当前亮度: 0")
        self.brightness_value.setAlignment(Qt.AlignCenter)
        self.brightness_value.setStyleSheet("font-size: 14px; font-weight: bold;")
        brightness_layout.addWidget(self.brightness_value)
        
        # 对比度滑块
        contrast_label = QLabel("对比度:")
        contrast_label.setStyleSheet("font-size: 14px;")
        brightness_layout.addWidget(contrast_label)
        
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(-100, 100)
        self.contrast_slider.setValue(0)
        self.contrast_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: #e0e0e0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                width: 20px;
                background: #e67e22;
                border-radius: 10px;
                margin: -6px 0;
            }
            QSlider::sub-page:horizontal {
                background: #e67e22;
                border-radius: 4px;
            }
        """)
        brightness_layout.addWidget(self.contrast_slider)
        
        self.contrast_value = QLabel("当前对比度: 0")
        self.contrast_value.setAlignment(Qt.AlignCenter)
        self.contrast_value.setStyleSheet("font-size: 14px; font-weight: bold;")
        brightness_layout.addWidget(self.contrast_value)
        
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)
        
        # 旋转和镜像
        transform_group = QGroupBox("旋转与镜像")
        transform_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        transform_layout = QGridLayout()
        transform_layout.setContentsMargins(10, 15, 10, 15)
        transform_layout.setVerticalSpacing(15)
        transform_layout.setHorizontalSpacing(15)
        
        # 旋转按钮
        rotate_label = QLabel("旋转角度:")
        rotate_label.setStyleSheet("font-size: 14px;")
        transform_layout.addWidget(rotate_label, 0, 0)
        
        self.rotate_combo = QComboBox()
        self.rotate_combo.setFixedHeight(35)
        self.rotate_combo.setStyleSheet("""
            QComboBox {
                font-size: 14px;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
            QComboBox::drop-down {
                width: 25px;
            }
        """)
        self.rotate_combo.addItems(["0°", "90°", "180°", "270°"])
        transform_layout.addWidget(self.rotate_combo, 0, 1)
        
        # 镜像按钮
        flip_label = QLabel("镜像翻转:")
        flip_label.setStyleSheet("font-size: 14px;")
        transform_layout.addWidget(flip_label, 1, 0)
        
        self.flip_combo = QComboBox()
        self.flip_combo.setFixedHeight(35)
        self.flip_combo.setStyleSheet("""
            QComboBox {
                font-size: 14px;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
            QComboBox::drop-down {
                width: 25px;
            }
        """)
        self.flip_combo.addItems(["无", "水平翻转", "垂直翻转"])
        transform_layout.addWidget(self.flip_combo, 1, 1)
        
        transform_group.setLayout(transform_layout)
        layout.addWidget(transform_group)
        
        # 分辨率设置
        resolution_group = QGroupBox("分辨率设置 (需重启摄像头)")
        resolution_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        resolution_layout = QGridLayout()
        resolution_layout.setContentsMargins(10, 15, 10, 15)
        resolution_layout.setVerticalSpacing(10)
        resolution_layout.setHorizontalSpacing(10)
        
        # 宽度输入
        width_label = QLabel("宽度:")
        width_label.setStyleSheet("font-size: 14px;")
        resolution_layout.addWidget(width_label, 0, 0)
        
        self.width_input = QLineEdit()
        self.width_input.setFixedHeight(35)
        self.width_input.setValidator(QIntValidator(100, 4096))
        self.width_input.setStyleSheet("""
            QLineEdit {
                font-size: 14px;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
        """)
        resolution_layout.addWidget(self.width_input, 0, 1)
        
        # 高度输入
        height_label = QLabel("高度:")
        height_label.setStyleSheet("font-size: 14px;")
        resolution_layout.addWidget(height_label, 1, 0)
        
        self.height_input = QLineEdit()
        self.height_input.setFixedHeight(35)
        self.height_input.setValidator(QIntValidator(100, 4096))
        self.height_input.setStyleSheet("""
            QLineEdit {
                font-size: 14px;
                padding: 5px;
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
        """)
        resolution_layout.addWidget(self.height_input, 1, 1)
        
        resolution_group.setLayout(resolution_layout)
        layout.addWidget(resolution_group)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        apply_btn = QPushButton("应用")
        apply_btn.setFixedHeight(40)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        apply_btn.clicked.connect(self.accept)
        btn_layout.addWidget(apply_btn)
        
        reset_btn = QPushButton("重置")
        reset_btn.setFixedHeight(40)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
        """)
        reset_btn.clicked.connect(self.reset)
        btn_layout.addWidget(reset_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # 连接信号
        self.brightness_slider.valueChanged.connect(lambda v: self.brightness_value.setText(f"当前亮度: {v}"))
        self.contrast_slider.valueChanged.connect(lambda v: self.contrast_value.setText(f"当前对比度: {v}"))
    
    def reset(self):
        """重置所有设置"""
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(0)
        self.rotate_combo.setCurrentIndex(0)
        self.flip_combo.setCurrentIndex(0)
        self.width_input.clear()
        self.height_input.clear()
    
    def get_settings(self):
        """获取设置"""
        width = self.width_input.text().strip()
        height = self.height_input.text().strip()
        
        return {
            "brightness": self.brightness_slider.value(),
            "contrast": self.contrast_slider.value(),
            "rotation": self.rotate_combo.currentIndex(),
            "flip": self.flip_combo.currentIndex(),
            "resolution": (int(width) if width else None, int(height) if height else None)
        }
    
    def set_resolution(self, width, height):
        """设置分辨率值"""
        if width:
            self.width_input.setText(str(width))
        if height:
            self.height_input.setText(str(height))

class VideoAnnotationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 设置应用为全屏模式
        self.showFullScreen()
        
        # 设置窗口标题
        self.setWindowTitle("希沃视频展台专业版")
        
        # 触控初始化
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.pinch_zoom = 1.0
        self.pan_offset = QPointF(0, 0)
        self.last_touch_points = {}
        self.touch_drawing = False
        
        # 性能优化配置
        self.camera_resolution = (1280, 720)
        self.target_fps = 30
        
        # 初始化变量
        self.cap = None
        self.current_frame = None
        self.drawing = False
        self.last_point = None
        self.annotations = []
        self.live_annotations = []  # 用于存储实时画面的批注
        self.current_tool = "pen"
        self.pen_color = QColor(255, 0, 0)
        self.pen_width = 8
        self.camera_active = False
        self.saved_image_path = None
        self.startup_image = None
        self.showing_startup = True
        self.current_camera_index = -1
        self.captured_images = []
        self.current_captured_image = None
        self.correction_points = None
        self.correction_matrix = None
        self.photo_dock = None
        self.zoom_factor = 1.0
        self.zoom_offset = QPointF(0, 0)
        self.current_annotation = None
        self.last_touch_area = 0.0
        self.palm_threshold = 1500
        self.image_adjust_settings = {
            "brightness": 0,
            "contrast": 0,
            "rotation": 0,
            "flip": 0,
            "resolution": (None, None)
        }
        self.camera_list = []
        self.temp_annotation = None
        self.last_draw_time = 0
        self.zoom_indicator = None
        self.zoom_indicator_timer = None
        self.background_pixmap = None  # 用于在绘制过程中冻结实时画面
        self.scanning = False  # 扫描状态标志
        self.scan_timer = None  # 扫描定时器
        
        # 加载配置
        self.load_config()
        
        # 创建UI
        self.init_ui()
        
        # 启动1秒计时器，然后自动连接摄像头
        self.startup_timer = QTimer(self)
        self.startup_timer.setSingleShot(True)
        self.startup_timer.timeout.connect(self.post_startup)
        self.startup_timer.start(1000)
    
    def post_startup(self):
        """启动图显示1秒后执行的操作"""
        self.video_label.setPixmap(QPixmap())
        self.video_label.setStyleSheet("background-color: black;")
        self.showing_startup = False
        self.auto_connect_camera()
    
    def load_config(self):
        """加载配置文件"""
        self.config = {
            "camera_index": -1, 
            "correction_points": None,
            "image_adjust": {
                "brightness": 0,
                "contrast": 0,
                "rotation": 0,
                "flip": 0,
                "resolution": (None, None)
            }
        }
        
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                    self.config = json.load(f)
                    self.current_camera_index = self.config.get("camera_index", -1)
                    self.correction_points = self.config.get("correction_points", None)
                    self.image_adjust_settings = self.config.get("image_adjust", self.image_adjust_settings)
        except:
            pass
    
    def save_config(self):
        """保存配置文件"""
        try:
            self.config["camera_index"] = self.current_camera_index
            self.config["correction_points"] = self.correction_points
            self.config["image_adjust"] = self.image_adjust_settings
            
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
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #3498db;
                titlebar-close-icon: url(none);
                titlebar-normal-icon: url(none);
            }
            QDockWidget::title {
                background-color: #2c3e50;
                text-align: left;
                padding-left: 10px;
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
                border: 2px solid #3498db;
                border-radius: 8px;
            }
        """)
        self.video_label.setMinimumSize(800, 600)
        
        # 安装事件过滤器来处理触控和鼠标事件
        self.video_label.installEventFilter(self)
        
        main_layout.addWidget(self.video_label, 1)
        
        # 创建底部工具栏 - 修改为白色主题
        self.toolbar = QToolBar("主工具栏")
        self.toolbar.setIconSize(QSize(36, 36))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.toolbar.setMovable(True)
        self.toolbar.setStyleSheet("""
            QToolBar {
                background-color: white;
                border-top: 2px solid #3498db;
                padding: 6px;
                spacing: 8px;
            }
            QToolButton {
                background-color: white;
                color: #2c3e50;
                border-radius: 6px;
                padding: 6px;
                font-size: 11px;
                font-weight: bold;
                min-width: 60px;
                min-height: 60px;
                border: 1px solid #d0d0d0;
            }
            QToolButton:hover {
                background-color: #f0f0f0;
                border: 1px solid #3498db;
            }
            QToolButton:pressed {
                background-color: #e0e0e0;
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
                background-color: white;
                color: #2c3e50;
                border: 1px solid #3498db;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 30px 8px 20px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        
        # 相机选择动作
        self.camera_action = QAction(QIcon(self.get_icon_path("switch_camera.png")), "切换摄像头", self)
        self.camera_action.setMenu(self.camera_menu)
        self.toolbar.addAction(self.camera_action)
        
        # 拍照按钮
        capture_action = QAction(QIcon(self.get_icon_path("capture.png")), "拍照", self)
        capture_action.triggered.connect(self.capture_image)
        capture_action.setShortcut(QKeySequence("Space"))
        self.toolbar.addAction(capture_action)
        
        # 保存按钮
        save_action = QAction(QIcon(self.get_icon_path("save.png")), "保存", self)
        save_action.triggered.connect(self.save_image)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        self.toolbar.addAction(save_action)
        
        self.toolbar.addSeparator()
        
        # 画笔按钮
        pen_action = QAction(QIcon(self.get_icon_path("pen.png")), "画笔", self)
        pen_action.triggered.connect(lambda: self.set_tool("pen"))
        pen_action.setShortcut(QKeySequence("P"))
        pen_action.setCheckable(True)
        pen_action.setChecked(True)
        self.toolbar.addAction(pen_action)
        
        # 移动/缩放按钮 (替换箭头按钮)
        move_action = QAction(QIcon(self.get_icon_path("move.png")), "移动", self)
        move_action.triggered.connect(lambda: self.set_tool("move"))
        move_action.setShortcut(QKeySequence("M"))
        move_action.setCheckable(True)
        self.toolbar.addAction(move_action)
        
        # 橡皮擦按钮 (修复：调小橡皮擦面积)
        eraser_action = QAction(QIcon(self.get_icon_path("eraser.png")), "橡皮擦", self)
        eraser_action.triggered.connect(lambda: self.set_tool("eraser"))
        eraser_action.setShortcut(QKeySequence("E"))
        eraser_action.setCheckable(True)
        self.toolbar.addAction(eraser_action)
        
        # 清除按钮
        clear_action = QAction(QIcon(self.get_icon_path("clear.png")), "清除", self)
        clear_action.triggered.connect(self.clear_annotations)
        clear_action.setShortcut(QKeySequence("Ctrl+D"))
        self.toolbar.addAction(clear_action)
        
        # 撤回按钮
        undo_action = QAction(QIcon(self.get_icon_path("undo.png")), "撤回", self)
        undo_action.triggered.connect(self.undo_annotation)
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        self.toolbar.addAction(undo_action)
        
        self.toolbar.addSeparator()
        
        # 梯形校正按钮
        correction_action = QAction(QIcon(self.get_icon_path("correction.png")), "梯形校正", self)
        correction_action.triggered.connect(self.apply_perspective_correction)
        self.toolbar.addAction(correction_action)
        
        # 图像调整按钮 (修复：确保对话框能正常弹出)
        adjust_action = QAction(QIcon(self.get_icon_path("adjust.png")), "画面调节", self)
        adjust_action.triggered.connect(self.adjust_image)
        self.toolbar.addAction(adjust_action)
        
        # 画笔设置按钮
        pen_settings_action = QAction(QIcon(self.get_icon_path("settings.png")), "画笔设置", self)
        pen_settings_action.triggered.connect(self.open_pen_settings)
        pen_settings_action.setShortcut(QKeySequence("Ctrl+P"))
        self.toolbar.addAction(pen_settings_action)
        
        # 照片面板按钮
        photos_action = QAction(QIcon(self.get_icon_path("photos.png")), "照片", self)
        photos_action.triggered.connect(self.toggle_photo_dock)
        self.toolbar.addAction(photos_action)
        
        # 扫描按钮
        scan_action = QAction(QIcon(self.get_icon_path("scan.png")), "扫描", self)
        scan_action.triggered.connect(self.start_scan)
        self.toolbar.addAction(scan_action)
        
        # 添加最小化按钮
        minimize_action = QAction(QIcon(self.get_icon_path("minimize.png")), "最小化", self)
        minimize_action.triggered.connect(self.showMinimized)
        minimize_action.setShortcut(QKeySequence("Ctrl+M"))
        self.toolbar.addAction(minimize_action)
        
        # 退出按钮
        exit_action = QAction(QIcon(self.get_icon_path("exit.png")), "退出", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut(QKeySequence("Esc"))
        self.toolbar.addAction(exit_action)
        
        # 添加状态栏
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #2c3e50;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border-top: 2px solid #3498db;
                padding: 4px;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("正在启动...")
        
        # 创建照片面板（右侧停靠）
        self.create_photo_dock()
        
        # 创建定时器用于更新视频
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        
        # 扫描定时器
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.update_scan)
        
        # 缩放指示器
        self.zoom_indicator = QLabel(self)
        self.zoom_indicator.setAlignment(Qt.AlignCenter)
        self.zoom_indicator.setStyleSheet("""
            QLabel {
                background-color: rgba(40, 40, 40, 180);
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 10px;
                padding: 8px;
            }
        """)
        self.zoom_indicator.hide()
        self.zoom_indicator_timer = QTimer(self)
        self.zoom_indicator_timer.setSingleShot(True)
        self.zoom_indicator_timer.timeout.connect(self.zoom_indicator.hide)
    
    def create_photo_dock(self):
        """创建照片停靠面板"""
        self.photo_dock = QDockWidget("照片库", self)
        self.photo_dock.setObjectName("PhotoDock")
        self.photo_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.photo_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.photo_dock.setMinimumWidth(300)
        self.addDockWidget(Qt.RightDockWidgetArea, self.photo_dock)
        
        # 创建主部件
        dock_widget = QWidget()
        self.photo_dock.setWidget(dock_widget)
        
        # 主布局
        layout = QVBoxLayout(dock_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 标题栏
        title_layout = QHBoxLayout()
        
        # 标题
        title_label = QLabel("捕获的照片")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
                padding: 5px;
            }
        """)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_layout.addWidget(title_label)
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 14px;
                font-size: 18px;
                font-weight: bold;
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
                border-radius: 8px;
            }
            QScrollBar:vertical {
                background: #2c3e50;
                width: 14px;
                margin: 0px 0px 0px 0px;
                border-radius: 7px;
            }
            QScrollBar::handle:vertical {
                background: #3498db;
                min-height: 30px;
                border-radius: 7px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 捕获图像列表容器
        self.captured_list_widget = QListWidget()
        self.captured_list_widget.setViewMode(QListWidget.IconMode)
        self.captured_list_widget.setIconSize(QSize(140, 105))
        self.captured_list_widget.setResizeMode(QListWidget.Adjust)
        self.captured_list_widget.setSpacing(10)
        self.captured_list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: none;
                padding: 10px;
            }
            QListWidget::item {
                border: 2px solid #444444;
                border-radius: 8px;
                background-color: #2c3e50;
                padding: 5px;
            }
            QListWidget::item:selected {
                border: 3px solid #3498db;
                background-color: #34495e;
            }
        """)
        self.captured_list_widget.itemClicked.connect(self.select_captured_image)
        
        scroll_area.setWidget(self.captured_list_widget)
        layout.addWidget(scroll_area, 1)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setFixedHeight(40)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        clear_btn.clicked.connect(self.clear_captured_images)
        btn_layout.addWidget(clear_btn)
        
        # 返回直播按钮 (修复：确保能正确返回实时画面)
        back_to_live_btn = QPushButton("返回直播")
        back_to_live_btn.setFixedHeight(40)
        back_to_live_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
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
    
    def get_icon_path(self, icon_name):
        """获取图标路径"""
        # 如果图标文件不存在，使用空路径
        if not os.path.exists(f"icons/{icon_name}"):
            return ""
        return f"icons/{icon_name}"
    
    def open_pen_settings(self):
        """打开画笔设置对话框 - 允许在没有摄像头时打开"""
        try:
            dialog = ColorWidthDialog(self, self.pen_color, self.pen_width)
            dialog.exec_()  # 直接打开，无需检查摄像头状态
        except Exception as e:
            print(f"打开画笔设置错误: {e}")
            self.status_bar.showMessage(f"打开画笔设置出错: {str(e)}")
    
    def apply_perspective_correction(self):
        """应用梯形校正"""
        # 允许在没有摄像头时打开，但需要当前帧
        if self.current_frame is None:
            # 如果没有当前帧，创建黑色背景
            pixmap = QPixmap(640, 480)
            pixmap.fill(Qt.black)
            painter = QPainter(pixmap)
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 16))
            painter.drawText(pixmap.rect(), Qt.AlignCenter, "无可用图像\n请先连接摄像头")
            painter.end()
        else:
            # 获取当前帧
            frame = self.current_frame.copy()
            
            # 创建QImage
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            qimage = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)
        
        # 创建校正对话框
        dialog = PerspectiveCorrectionDialog(self, self.camera_resolution)
        
        # 设置之前保存的校正点
        if self.correction_points:
            dialog.set_correction_points(self.correction_points)
        
        # 设置对话框图像
        dialog.set_image(pixmap)
        
        # 显示对话框
        if dialog.exec_() == QDialog.Accepted:
            self.correction_points = dialog.get_correction_points()
            self.correction_matrix = dialog.get_correction_matrix(self.camera_resolution)
            self.status_bar.showMessage("梯形校正已应用")
            self.save_config()
        else:
            self.correction_matrix = None
            self.status_bar.showMessage("梯形校正已取消")
    
    def switch_camera(self, index):
        """切换到指定摄像头"""
        if self.camera_active:
            self.stop_camera()
            
        # 显示加载状态
        self.status_bar.showMessage(f"正在连接摄像头 {index}...")
        QApplication.processEvents()
        
        # 获取分辨率设置
        res = self.image_adjust_settings.get("resolution", (None, None))
        width, height = res
        
        # 使用线程初始化摄像头
        self.camera_thread = CameraInitThread(index, width, height)
        self.camera_thread.finished.connect(self.on_camera_connected)
        self.camera_thread.error.connect(self.on_camera_error)
        self.camera_thread.start()
    
    def on_camera_connected(self, cap):
        """摄像头连接成功"""
        self.cap = cap
        self.camera_active = True
        self.timer.start(int(1000 / self.target_fps))
        
        # 获取实际分辨率
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.camera_resolution = (width, height)
        
        self.status_bar.showMessage(f"已连接摄像头 {self.current_camera_index} - {width}x{height} @ {self.target_fps}fps")
        
        # 如果存在校正点，计算校正矩阵
        if self.correction_points:
            dialog = PerspectiveCorrectionDialog(self, self.camera_resolution)
            dialog.set_correction_points(self.correction_points)
            self.correction_matrix = dialog.get_correction_matrix(self.camera_resolution)
            self.status_bar.showMessage("梯形校正已加载")
    
    def on_camera_error(self, error_msg):
        """摄像头连接错误"""
        self.status_bar.showMessage(error_msg)
        # 尝试下一个摄像头
        self.try_next_camera()
    
    def try_next_camera(self):
        """尝试连接下一个可用摄像头"""
        if not self.camera_list:
            self.camera_list = self.detect_cameras()
            
        if not self.camera_list:
            return
            
        # 获取当前索引在列表中的位置
        if self.current_camera_index in self.camera_list:
            current_index = self.camera_list.index(self.current_camera_index)
            next_index = (current_index + 1) % len(self.camera_list)
            next_camera = self.camera_list[next_index]
            self.switch_camera(next_camera)
        else:
            self.switch_camera(self.camera_list[0])
    
    def start_camera(self):
        """启动摄像头"""
        if self.camera_active:
            self.timer.start(int(1000 / self.target_fps))
            self.status_bar.showMessage(f"摄像头已重新启动 - {self.camera_resolution[0]}x{self.camera_resolution[1]}")
        else:
            self.status_bar.showMessage("摄像头启动失败")
    
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
            action = self.camera_menu.addAction(f"摄像头 {i}")
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
            time.sleep(0.5)
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
    
    def update_frame(self):
        """更新视频帧"""
        if self.cap and self.cap.isOpened() and not self.drawing:    
            ret, frame = self.cap.read()
            if not ret:
                self.status_bar.showMessage("摄像头读取错误")
                return
            
            # 应用梯形校正
            if self.correction_matrix is not None:
                frame = cv2.warpPerspective(frame, self.correction_matrix, 
                                           (self.camera_resolution[0], self.camera_resolution[1]))
            
            # 应用图像调整
            frame = self.apply_image_adjustments(frame)
            
            # 转换颜色空间 BGR -> RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            
            # 创建QImage
            image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(image)
            self.current_frame = frame
        else:
            # 如果没有摄像头，使用黑色背景
            pixmap = QPixmap(self.video_label.size())
            pixmap.fill(Qt.black)
            self.current_frame = None
        
        # 绘制已有的批注
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, False)
        
        # 绘制所有批注
        for annotation in self.annotations:
            self.draw_annotation(painter, annotation)
        
        # 绘制临时批注
        if self.temp_annotation:
            self.draw_annotation(painter, self.temp_annotation)
        
        painter.end()
        
        # 显示图像（考虑缩放）
        scaled_pixmap = pixmap.scaled(
            int(self.video_label.width() * self.zoom_factor),
            int(self.video_label.height() * self.zoom_factor),
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
    
    def draw_annotation(self, painter, annotation):
        """绘制单个批注"""
        tool = annotation["tool"]
        points = annotation["points"]
        color = annotation["color"]
        width = annotation["width"]
        
        pen = QPen(color)
        pen.setWidth(width)
        painter.setPen(pen)
        
        if tool == "pen" and len(points) > 1:
            path = QPainterPath()
            path.moveTo(points[0])
            for i in range(1, len(points)):
                path.lineTo(points[i])
            painter.drawPath(path)
        # 修复：调小橡皮擦面积 (从3倍改为1.5倍)
        elif tool == "eraser" and len(points) > 1:
            pen = QPen(Qt.black)
            pen.setWidth(int(width * 1.5))  # 减小橡皮擦面积
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(points[0])
            for i in range(1, len(points)):
                path.lineTo(points[i])
            painter.drawPath(path)
    
    def apply_image_adjustments(self, frame):
        """应用图像调整设置 - 增强亮度效果"""
        if frame is None:
            return frame
        
        # 调整亮度和对比度
        brightness = self.image_adjust_settings["brightness"]
        contrast = self.image_adjust_settings["contrast"]
        
        # 增强亮度调整效果
        if brightness != 0 or contrast != 0:
            # 将亮度和对比度值映射到更有效的范围
            alpha = 1.0 + contrast / 100.0 * 2.0  # 对比度因子 (0.0 到 3.0)
            beta = brightness * 2.55  # 亮度调整 (-255 到 255)
            
            # 应用调整
            frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
        
        # 旋转图像
        rotation = self.image_adjust_settings["rotation"]
        if rotation == 1:  # 90度
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rotation == 2:  # 180度
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif rotation == 3:  # 270度
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        # 镜像翻转
        flip = self.image_adjust_settings["flip"]
        if flip == 1:  # 水平翻转
            frame = cv2.flip(frame, 1)
        elif flip == 2:  # 垂直翻转
            frame = cv2.flip(frame, 0)
        
        return frame
    
    def adjust_image(self):
        """打开图像调整对话框 - 允许在没有摄像头时打开"""
        try:
            dialog = ImageAdjustDialog(self)
            
            # 设置当前值
            dialog.brightness_slider.setValue(self.image_adjust_settings["brightness"])
            dialog.contrast_slider.setValue(self.image_adjust_settings["contrast"])
            dialog.rotate_combo.setCurrentIndex(self.image_adjust_settings["rotation"])
            dialog.flip_combo.setCurrentIndex(self.image_adjust_settings["flip"])
            
            # 设置分辨率值
            res = self.image_adjust_settings.get("resolution", (None, None))
            dialog.set_resolution(res[0], res[1])
            
            if dialog.exec_() == QDialog.Accepted:
                settings = dialog.get_settings()
                self.image_adjust_settings = settings
                self.status_bar.showMessage(f"图像调整已应用 - 亮度: {settings['brightness']}, 对比度: {settings['contrast']}")
                self.save_config()
                
                # 如果分辨率有变化，重新连接摄像头
                if settings["resolution"] != (None, None) and self.camera_active:
                    self.status_bar.showMessage("分辨率设置将在下次连接摄像头时生效")
                    self.stop_camera()
                    self.switch_camera(self.current_camera_index)
            else:
                self.status_bar.showMessage("图像调整已取消")
        except Exception as e:
            print(f"画面调节错误: {e}")
            self.status_bar.showMessage(f"画面调节出错: {str(e)}")
    
    def capture_image(self):
        """捕获当前画面"""
        # 即使没有摄像头，也可以捕获当前显示的内容
        current_pixmap = self.video_label.pixmap()
        if not current_pixmap or current_pixmap.isNull():
            blank_image = QImage(640, 480, QImage.Format_RGB888)
            blank_image.fill(Qt.black)
            current_pixmap = QPixmap.fromImage(blank_image)
        
        # 创建捕获图像对象 - 包括当前批注
        captured = CapturedImage(current_pixmap)
        
        # 添加当前批注到捕获的图像
        for annotation in self.annotations:
            captured.add_annotation(annotation.copy())
        
        self.captured_images.append(captured)
        
        # 更新照片面板
        if self.photo_dock and self.photo_dock.isVisible():
            self.update_photo_dock()
        
        self.status_bar.showMessage(f"已捕获图像 - {captured.timestamp}")
    
    def start_scan(self):
        """开始扫描过程"""
        if self.scanning:
            return
            
        if not self.camera_active:
            self.status_bar.showMessage("请先连接摄像头")
            return
            
        self.status_bar.showMessage("扫描中...")
        self.scanning = True
        self.scan_lines = []
        self.scan_progress = 0
        self.scan_timer.start(50)  # 每50毫秒更新一次
    
    def update_scan(self):
        """更新扫描动画"""
        if not self.scanning or not self.camera_active:
            return
            
        # 获取当前帧
        ret, frame = self.cap.read()
        if not ret:
            self.scan_timer.stop()
            self.scanning = False
            self.status_bar.showMessage("扫描失败: 无法读取摄像头")
            return
            
        # 应用梯形校正
        if self.correction_matrix is not None:
            frame = cv2.warpPerspective(frame, self.correction_matrix, 
                                       (self.camera_resolution[0], self.camera_resolution[1]))
        
        # 应用图像调整
        frame = self.apply_image_adjustments(frame)
        
        # 转换颜色空间 BGR -> RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        
        # 添加当前扫描线
        line_height = max(1, h // 50)  # 每次扫描的高度
        start_line = min(self.scan_progress, h)
        end_line = min(self.scan_progress + line_height, h)
        
        # 保存当前扫描区域
        scan_line = frame[start_line:end_line, :, :].copy()
        self.scan_lines.append(scan_line)
        
        # 创建扫描效果图像
        scan_image = np.zeros((h, w, 3), dtype=np.uint8)
        current_line = 0
        for line in self.scan_lines:
            line_height = line.shape[0]
            scan_image[current_line:current_line+line_height, :, :] = line
            current_line += line_height
        
        # 绘制扫描线
        cv2.line(scan_image, (0, end_line), (w, end_line), (0, 255, 0), 2)
        
        # 转换为QPixmap并显示
        bytes_per_line = ch * w
        qimage = QImage(scan_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)
        self.video_label.setPixmap(pixmap.scaled(
            self.video_label.size(), 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        ))
        
        # 更新进度
        self.scan_progress += line_height
        if self.scan_progress >= h:
            # 扫描完成
            self.scan_timer.stop()
            self.scanning = False
            
            # 创建最终扫描图像
            final_scan = np.zeros((h, w, 3), dtype=np.uint8)
            current_line = 0
            for line in self.scan_lines:
                line_height = line.shape[0]
                final_scan[current_line:current_line+line_height, :, :] = line
                current_line += line_height
            
            # 保存扫描结果
            qimage = QImage(final_scan.data, w, h, bytes_per_line, QImage.Format_RGB888)
            scan_pixmap = QPixmap.fromImage(qimage)
            
            captured = CapturedImage(scan_pixmap)
            self.captured_images.append(captured)
            
            # 更新照片面板
            if self.photo_dock and self.photo_dock.isVisible():
                self.update_photo_dock()
            
            self.status_bar.showMessage(f"扫描完成 - {captured.timestamp}")
            
            # 返回实时画面
            self.back_to_live()
    
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
        """选择捕获的图像 - 只查看不批注"""
        index = item.data(Qt.UserRole)
        if 0 <= index < len(self.captured_images):
            # 停止摄像头
            if self.camera_active:
                self.stop_camera()
            
            self.current_captured_image = self.captured_images[index]
            
            # 显示捕获的图像
            pixmap = self.current_captured_image.get_annotated_pixmap()
            self.video_label.setPixmap(pixmap.scaled(
                self.video_label.width(), 
                self.video_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
            self.status_bar.showMessage(f"正在查看捕获的图像 - {self.current_captured_image.timestamp}")
    
    def back_to_live(self):
        """返回直播画面 - 修复返回功能"""
        # 清除实时批注
        self.annotations = []
        self.zoom_factor = 1.0
        self.zoom_offset = QPointF(0, 0)
        self.current_captured_image = None
        
        # 恢复直播批注
        self.annotations = self.live_annotations.copy()
        
        # 重新连接摄像头
        if not self.camera_active and self.current_camera_index >= 0:
            self.switch_camera(self.current_camera_index)
        elif self.camera_active:
            # 如果摄像头已经在运行，只需更新画面
            self.update_frame()
        
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
        """事件过滤器处理触控和鼠标事件 - 优化缩放UI"""
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
        # 在查看照片时忽略触控事件
        if self.current_captured_image:
            return
            
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
        
        # 单指触控 - 开始绘制
        if len(self.last_touch_points) == 1 and self.current_tool != "move":
            self.touch_drawing = True
            pos = list(self.last_touch_points.values())[0]
            self.start_drawing(pos)
    
    def handle_touch_update(self, event):
        """处理触控更新事件"""
        # 在查看照片时忽略触控事件
        if self.current_captured_image:
            return
            
        current_time = time.time()
        if current_time - self.last_draw_time < 0.02:
            return
            
        touch_points = {}
        
        for touch_point in event.touchPoints():
            touch_points[touch_point.id()] = touch_point.pos()
        
        # 双指手势识别
        if len(touch_points) == 2:
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
        # 单指触控 - 继续绘制
        elif self.touch_drawing and len(touch_points) == 1 and self.current_tool != "move":
            pos = list(touch_points.values())[0]
            self.continue_drawing(pos)
            self.last_draw_time = current_time
        
        self.last_touch_points = touch_points
    
    def handle_touch_end(self, event):
        """处理触控结束事件"""
        self.touch_drawing = False
        self.last_touch_points = {}
        self.finalize_drawing()
        
        # 恢复原工具
        if hasattr(self, 'previous_tool') and self.current_tool == "eraser":
            self.current_tool = self.previous_tool
            self.status_bar.showMessage(f"已恢复为 {self.current_tool} 模式")
    
    def handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        # 在查看照片时忽略鼠标事件
        if self.current_captured_image:
            return
            
        # 移动模式下处理拖动
        if self.current_tool == "move":
            self.drag_start = event.pos()
            self.drag_offset = self.zoom_offset
            return
            
        self.start_drawing(event.pos())
    
    def handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        # 在查看照片时忽略鼠标事件
        if self.current_captured_image:
            return
            
        current_time = time.time()
        if current_time - self.last_draw_time < 0.02:
            return
            
        # 移动模式下处理拖动
        if self.current_tool == "move" and event.buttons() & Qt.LeftButton:
            delta = event.pos() - self.drag_start
            self.zoom_offset = self.drag_offset + QPointF(delta)
            self.update_frame()
            return
            
        if self.drawing:
            self.continue_drawing(event.pos())
            self.last_draw_time = current_time
    
    def handle_mouse_release(self, event):
        """处理鼠标释放事件"""
        self.finalize_drawing()
    
    def finalize_drawing(self):
        """完成绘制"""
        if self.temp_annotation:
            # 添加到批注列表
            self.annotations.append(self.temp_annotation)
            # 保存到直播批注列表
            self.live_annotations = self.annotations.copy()
            # 强制更新实时画面
            self.update_frame()
            
            self.temp_annotation = None
            # 确保立即更新显示
            QApplication.processEvents()
        
        self.drawing = False
        self.last_point = None
        
        # 恢复实时画面的定时器
        if self.camera_active and not self.current_captured_image:
            self.timer.start(int(1000 / self.target_fps))
            self.background_pixmap = None
    
    def handle_wheel_event(self, event):
        """处理鼠标滚轮事件进行缩放"""
        # 在查看照片时忽略滚轮事件
        if self.current_captured_image:
            return
            
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
        
        self.update_frame()
        self.show_zoom_indicator()
    
    def show_zoom_indicator(self):
        """显示缩放指示器"""
        zoom_percent = int(self.zoom_factor * 100)
        self.zoom_indicator.setText(f"缩放: {zoom_percent}%")
        self.zoom_indicator.adjustSize()
        
        # 位置在右上角
        x = self.video_label.width() - self.zoom_indicator.width() - 20
        y = 20
        
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
        
        # 如果是实时画面且没有当前捕获的图像，则暂停定时器并保存背景
        if self.camera_active and not self.current_captured_image:
            self.timer.stop()  # 暂停定时器
            # 保存当前画面作为背景（包含之前的所有批注）
            current_pixmap = self.video_label.pixmap()
            if current_pixmap and not current_pixmap.isNull():
                self.background_pixmap = current_pixmap.copy()
        
        # 创建临时批注
        if self.current_tool == "eraser":
            self.temp_annotation = {
                "tool": self.current_tool,
                "points": [img_pos],
                "color": QColor(0, 0, 0),
                "width": int(self.pen_width * 1.5),  # 减小橡皮擦面积
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
    
    def continue_drawing(self, pos):
        """继续绘制批注"""
        if not self.drawing or self.current_tool is None or not self.temp_annotation:
            return
        
        # 计算实际图像位置
        img_pos = self.map_to_image(pos)
        if not img_pos:
            return
        
        # 添加点到临时批注
        self.temp_annotation["points"].append(img_pos)
        
        # 对于实时画面：在静态背景上绘制
        if self.camera_active and not self.current_captured_image and self.background_pixmap:
            pixmap = self.background_pixmap.copy()
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 绘制所有批注
            for annotation in self.annotations:
                self.draw_annotation(painter, annotation)
            
            # 绘制临时批注
            self.draw_annotation(painter, self.temp_annotation)
            
            painter.end()
            self.video_label.setPixmap(pixmap)
        
        # 确保立即更新显示
        QApplication.processEvents()
    
    def map_to_image(self, pos):
        """将屏幕坐标映射到图像坐标（修复不同步问题）"""
        if not self.video_label.pixmap() or self.video_label.pixmap().isNull():
            return None
        
        # 获取标签尺寸和图像尺寸
        label_rect = self.video_label.rect()
        pixmap = self.video_label.pixmap()
        pixmap_size = pixmap.size()
        
        # 计算缩放后的图像尺寸（保持比例）
        scaled = pixmap_size.scaled(label_rect.size(), Qt.KeepAspectRatio)
        
        # 计算偏移（居中）
        x_offset = (label_rect.width() - scaled.width()) / 2
        y_offset = (label_rect.height() - scaled.height()) / 2
        
        # 计算缩放比例
        scale_factor_x = scaled.width() / pixmap_size.width()
        scale_factor_y = scaled.height() / pixmap_size.height()
        
        # 转换为图像坐标（考虑缩放和偏移）
        img_x = (pos.x() - x_offset) / scale_factor_x
        img_y = (pos.y() - y_offset) / scale_factor_y
        
        # 检查是否在图像范围内
        if 0 <= img_x < pixmap_size.width() and 0 <= img_y < pixmap_size.height():
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
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(Qt.black, 2))
            painter.setBrush(Qt.white)
            painter.drawEllipse(0, 0, 32, 32)
            painter.end()
            self.setCursor(QCursor(pixmap))
        elif tool == "move":
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
    
    def clear_annotations(self):
        """清除所有批注"""
        if not self.annotations:
            return
            
        self.annotations = []
        self.live_annotations = []  # 同时清除直播批注
        self.status_bar.showMessage("已清除实时画面的批注")
        # 强制更新显示
        self.update_frame()
        
        # 确保立即更新显示
        QApplication.processEvents()
    
    def undo_annotation(self):
        """撤回最后一步批注"""
        if self.annotations:
            self.annotations.pop()
            self.live_annotations = self.annotations.copy()  # 更新直播批注
            self.status_bar.showMessage("已撤回上一步操作")
            # 强制更新显示
            self.update_frame()
            # 确保立即更新显示
            QApplication.processEvents()
            return True
        
        self.status_bar.showMessage("没有可撤回的操作")
        return False
    
    def save_image(self):
        """保存当前图像（带批注）"""
        if self.current_captured_image:
            pixmap = self.current_captured_image.get_annotated_pixmap()
        elif self.current_frame is not None:
            frame = self.current_frame.copy()
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            
            qimage = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing, False)
            
            for annotation in self.annotations:
                self.draw_annotation(painter, annotation)
            
            painter.end()
        else:
            pixmap = self.video_label.pixmap()
            if pixmap is None or pixmap.isNull():
                self.status_bar.showMessage("没有可保存的图像")
                return
        
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
                pixmap.save(file_path, "JPEG", 90)
            else:
                pixmap.save(file_path, "PNG")
            
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
    
    def update_display(self):
        """强制更新显示"""
        self.update_frame()

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
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for annotation in self.annotations:
            tool = annotation["tool"]
            points = annotation["points"]
            color = annotation["color"]
            width = annotation["width"]
            
            pen = QPen(color)
            pen.setWidth(width)
            painter.setPen(pen)
            
            if tool == "pen" and len(points) > 1:
                path = QPainterPath()
                path.moveTo(points[0])
                for i in range(1, len(points)):
                    path.lineTo(points[i])
                painter.drawPath(path)
            # 修复：调小橡皮擦面积 (从3倍改为1.5倍)
            elif tool == "eraser" and len(points) > 1:
                pen = QPen(Qt.black)
                pen.setWidth(int(width * 1.5))  # 减小橡皮擦面积
                painter.setPen(pen)
                path = QPainterPath()
                path.moveTo(points[0])
                for i in range(1, len(points)):
                    path.lineTo(points[i])
                painter.drawPath(path)
        
        painter.end()
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
    
    def get_original_pixmap(self):
        """获取原始图像（无批注）"""
        return self.original_pixmap.copy()

if __name__ == "__main__":
    # 设置环境变量以优化性能
    os.environ["QT_LOGGING_RULES"] = "*.debug=false"
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    # 显示启动图
    splash = SplashScreen()
    splash.show()
    
    # 强制显示启动图
    QApplication.processEvents()
    
    # 等待3秒
    time.sleep(3)
    
    # 创建并显示主窗口
    window = VideoAnnotationApp()
    window.show()
    
    # 关闭启动图
    splash.close()
    
    sys.exit(app.exec_())
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import json
import os
import traceback

# 配置文件路径
CONFIG_FILE = 'config.json'

def load_config():
    """加载配置文件，若文件不存在或格式错误则返回空字典"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print("⚠️ 配置文件加载失败，可能格式错误，将使用默认值")
            traceback.print_exc()
            return {}
    return {}

def save_perspective_points(points):
    """仅更新 config.json 中的 perspective_points 字段"""
    new_points = [{"x": float(x), "y": float(y)} for x, y in points]

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"perspective_points": new_points}, f, indent=4)
        return

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except:
        config = {}

    # 仅更新 perspective_points 字段
    config['perspective_points'] = new_points

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def get_available_cameras(max_test=10):
    """检测可用摄像头，使用 CAP_DSHOW 后端以兼容 Windows 7"""
    available = []
    for i in range(max_test):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            available.append(i)
            cap.release()
    return available

class App:
    def __init__(self, root):
        self.root = root
        self.config = load_config()
        self.available_cameras = get_available_cameras()
        self.create_ui()

    def create_ui(self):
        """创建摄像头选择界面"""
        self.root.title("摄像头校准助手")
        self.root.geometry("300x200")  # 显式设置窗口大小

        tk.Label(self.root, text="请选择摄像头设备：", font=("Arial", 12)).pack(pady=10)

        for idx in self.available_cameras:
            tk.Button(self.root,
                     text=f"摄像头 {idx}",
                     command=lambda i=idx: self.start_calibration(i),
                     width=20,
                     height=2).pack(pady=5)

        tk.Button(self.root,
                 text="退出程序",
                 command=self.root.quit,
                 width=20,
                 height=2,
                 fg="red").pack(pady=20)

        print("✅ 主界面已加载")

    def start_calibration(self, camera_index):
        print(f"🚀 启动校准窗口，摄像头索引: {camera_index}")
        self.root.withdraw()
        CalibrationWindow(camera_index, self.config, self.on_calibration_save)

    def on_calibration_save(self, new_points):
        save_perspective_points(new_points)
        print("💾 配置已保存")
        self.root.deiconify()


class CalibrationWindow:
    def __init__(self, camera_index, config, save_callback):
        self.camera_index = camera_index
        self.config = config
        self.save_callback = save_callback
        self.dragging = None

        # 初始化摄像头（使用 CAP_DSHOW 以兼容 Windows 7）
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            print(f"❌ 无法打开摄像头 {camera_index}")
            return

        # 获取摄像头分辨率
        self.cam_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.cam_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 缩放因子，确保画面适合显示
        max_display_size = 800
        self.scale = min(max_display_size / self.cam_width, max_display_size / self.cam_height)
        self.display_width = int(self.cam_width * self.scale)
        self.display_height = int(self.cam_height * self.scale)

        print(f"📸 摄像头分辨率: {self.cam_width}x{self.cam_height}")
        print(f"🖥️  显示分辨率: {self.display_width}x{self.display_height}")

        # 初始化校准点
        if "perspective_points" in self.config:
            try:
                if isinstance(self.config["perspective_points"], list):
                    self.points = [[p['x'], p['y']] for p in self.config['perspective_points']]
                    print("✅ 成功加载配置中的校准点")
                else:
                    raise ValueError("perspective_points 不是列表")
            except Exception as e:
                print("⚠️ 配置文件中 perspective_points 格式错误，使用默认值")
                self.points = self.default_points()
        else:
            print("⚠️ 配置文件中缺少 perspective_points，使用默认值")
            self.points = self.default_points()

        # 创建GUI
        self.root = tk.Toplevel()
        self.root.title(f"摄像头校准 - 设备 {camera_index}")
        self.root.geometry(f"{self.display_width}x{self.display_height + 50}")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(self.root, width=self.display_width, height=self.display_height)
        self.canvas.pack()

        # 控制按钮
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="保存配置", command=self.save_config, width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="重置点位", command=self.reset_points, width=15).pack(side=tk.LEFT, padx=5)

        # 事件绑定
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)

        self.update_frame()
        self.root.mainloop()

    def default_points(self):
        """默认四角点"""
        margin = 0.05
        return [
            [self.cam_width * margin, self.cam_height * margin],
            [self.cam_width * (1 - margin), self.cam_height * margin],
            [self.cam_width * (1 - margin), self.cam_height * (1 - margin)],
            [self.cam_width * margin, self.cam_height * (1 - margin)]
        ]

    def update_frame(self):
        try:
            ret, frame = self.cap.read()
            if ret:
                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img).resize((self.display_width, self.display_height))
                self.photo = ImageTk.PhotoImage(img)
                self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)
                self.draw_points()
            else:
                print("⚠️ 无法读取摄像头画面")
        except Exception as e:
            print("❌ update_frame 出错:")
            traceback.print_exc()
        self.root.after(10, self.update_frame)

    def draw_points(self):
        self.canvas.delete('calibration_point')
        for i, (x, y) in enumerate(self.points):
            dx = int(x * self.scale)
            dy = int(y * self.scale)
            self.canvas.create_oval(
                dx - 7, dy - 7, dx + 7, dy + 7,
                fill='red', outline='white',
                tags=(f'point{i}', 'calibration_point')
            )

    def on_click(self, event):
        x, y = event.x, event.y
        for i, (px, py) in enumerate(self.points):
            dx = int(px * self.scale)
            dy = int(py * self.scale)
            if abs(dx - x) <= 10 and abs(dy - y) <= 10:
                self.dragging = i
                break

    def on_drag(self, event):
        if self.dragging is not None:
            x = max(0, min(event.x / self.scale, self.cam_width))
            y = max(0, min(event.y / self.scale, self.cam_height))
            self.points[self.dragging] = [x, y]
            self.draw_points()

    def on_release(self, event):
        self.dragging = None

    def reset_points(self):
        self.points = self.default_points()
        self.draw_points()
        print("🔄 已重置校准点")

    def save_config(self):
        new_points = [{"x": float(x), "y": float(y)} for x, y in self.points]
        self.save_callback(new_points)
        self.root.destroy()
        print("✅ 校准点已保存到配置文件")

    def on_close(self):
        self.cap.release()
        self.root.destroy()
        self.save_callback(self.points)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口直到初始化完成
    app = App(root)
    root.deiconify()  # 显示主窗口
    root.mainloop()
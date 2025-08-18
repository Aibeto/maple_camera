using AForge; // IntPoint
using AForge.Imaging.Filters;
using Newtonsoft.Json;
using ShowWrite.Models;
using ShowWrite.Services;
using ShowWrite.Views;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Ink;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Cursors = System.Windows.Input.Cursors;
using D = System.Drawing;
using MessageBox = System.Windows.MessageBox;
using WinForms = System.Windows.Forms;

namespace ShowWrite
{
    // 配置模型：保存摄像头索引与透视校正
    public class AppConfig
    {
        public int CameraIndex { get; set; } = 0;
        public List<IntPoint>? CorrectionPoints { get; set; }  // AForge.IntPoint（长度=4）
        public int SourceWidth { get; set; }
        public int SourceHeight { get; set; }
    }

    public partial class MainWindow : Window
    {
        private readonly VideoService _videoService = new();
        private readonly ObservableCollection<CapturedImage> _photos = new();
        private CapturedImage? _currentPhoto;
        private bool _isLiveMode = true;
        private int currentCameraIndex = 0; // 切换摄像头

        // 透视校正过滤器
        private QuadrilateralTransformation? _perspectiveCorrectionFilter;

        private enum ToolMode { None, Move, Pen, Eraser }
        private ToolMode _currentMode = ToolMode.None;

        private D.Point _lastMousePos;
        private bool _isPanning = false;

        // 缩放比例 & 用户笔宽
        private double currentZoom = 1.0;
        private double userPenWidth = 2.0;

        // —— 编辑历史 —— //
        private readonly Stack<EditAction> editHistory = new Stack<EditAction>();
        private EditAction? currentEdit = null;
        private bool isEditing = false;

        private class EditAction
        {
            public List<Stroke> AddedStrokes { get; } = new();
            public List<Stroke> RemovedStrokes { get; } = new();
        }

        // —— 画面调节（仅运行时，不写入 config） —— //
        // 说明：这里将亮度、对比度用“百分比偏移量”表示（-100~100），与 AForge 对应
        private double _brightness = 0.0;       // -100 ~ 100
        private double _contrast = 0.0;         // -100 ~ 100（AForge ContrastCorrection 使用偏移量）
        private int _rotation = 0;              // 0 / 90 / 180 / 270
        private bool _mirrorHorizontal = false; // 镜像：水平
        private bool _mirrorVertical = false;   // 镜像：垂直

        // 配置文件路径
        private readonly string configPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "config.json");

#pragma warning disable CS8618
        public MainWindow()
#pragma warning restore CS8618
        {
            InitializeComponent();
            PhotoList.ItemsSource = _photos;

            WindowStyle = WindowStyle.None;
            WindowState = WindowState.Maximized;

            // —— 捕捉画笔/橡皮事件 —— //
            Ink.StrokeCollected += Ink_StrokeCollected; // 画笔：落笔->抬笔后收集（一次性）
            Ink.PreviewMouseLeftButtonDown += Ink_PreviewMouseDown;
            Ink.PreviewMouseLeftButtonUp += Ink_PreviewMouseUp;
            Ink.PreviewStylusDown += Ink_PreviewStylusDown;
            Ink.PreviewStylusUp += Ink_PreviewStylusUp;

            // 仅用于橡皮：画笔在 StrokeCollected 里处理，避免重复/时序问题
            Ink.Strokes.StrokesChanged += Ink_StrokesChanged;

            SetMode(ToolMode.Pen, initial: true);

            _videoService.OnNewFrameProcessed += frame =>
            {
                Dispatcher.Invoke(() =>
                {
                    if (_isLiveMode)
                    {
                        // 处理当前帧：校正 + 调节（仅显示用，不修改原 frame）
                        using var processed = ProcessFrame((D.Bitmap)frame.Clone(), applyAdjustments: true);
                        VideoImage.Source = BitmapToBitmapImage(processed);
                    }
                });
            };

            // 先加载配置（摄像头索引 + 透视校正）
            LoadConfig();

            if (!_videoService.Start(currentCameraIndex))
            {
                MessageBox.Show("未找到可用摄像头。", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
            }

            UpdatePenAttributes();
        }

        private void UpdatePenAttributes()
        {
            // 保持视觉笔宽与缩放无关
            Ink.DefaultDrawingAttributes.Width = userPenWidth / currentZoom;
            Ink.DefaultDrawingAttributes.Height = userPenWidth / currentZoom;
        }

        // =========================
        // 编辑操作管理（一次性撤销手势）
        // =========================
        private void StartEdit()
        {
            if (isEditing) return;
            currentEdit = new EditAction();
            isEditing = true;
        }

        private void EndEdit()
        {
            if (!isEditing || currentEdit == null) return;

            if (currentEdit.AddedStrokes.Count > 0 || currentEdit.RemovedStrokes.Count > 0)
            {
                editHistory.Push(currentEdit);
            }

            currentEdit = null;
            isEditing = false;
        }

        private void Ink_PreviewMouseDown(object sender, MouseButtonEventArgs e) => StartEdit();

        private void Ink_PreviewMouseUp(object sender, MouseButtonEventArgs e)
        {
            // 画笔：不在这里结束，等 StrokeCollected；橡皮：在这里结束
            if (_currentMode != ToolMode.Pen)
                EndEdit();
        }

        private void Ink_PreviewStylusDown(object sender, StylusDownEventArgs e) => StartEdit();

        private void Ink_PreviewStylusUp(object sender, StylusEventArgs e)
        {
            if (_currentMode != ToolMode.Pen)
                EndEdit();
        }

        // 画笔：在收集到 Stroke 时一次性加入并结束本次手势
        private void Ink_StrokeCollected(object sender, InkCanvasStrokeCollectedEventArgs e)
        {
            if (_currentMode != ToolMode.Pen) return;
            if (!isEditing || currentEdit == null) StartEdit();

            currentEdit!.AddedStrokes.Add(e.Stroke);
            EndEdit();
        }

        // 橡皮：StrokesChanged 会持续触发，等 MouseUp 再 EndEdit()
        private void Ink_StrokesChanged(object? sender, StrokeCollectionChangedEventArgs e)
        {
            if (_currentMode == ToolMode.Pen) return;          // 画笔交给 StrokeCollected 处理
            if (!isEditing || currentEdit == null) return;

            foreach (var s in e.Added) currentEdit.AddedStrokes.Add(s);
            foreach (var s in e.Removed) currentEdit.RemovedStrokes.Add(s);
        }

        // =========================
        // 模式切换
        // =========================
        private void SetMode(ToolMode mode, bool initial = false)
        {
            _currentMode = mode;
            MoveBtn.IsChecked = mode == ToolMode.Move;
            PenBtn.IsChecked = mode == ToolMode.Pen;
            EraserBtn.IsChecked = mode == ToolMode.Eraser;

            switch (mode)
            {
                case ToolMode.Move:
                    Ink.EditingMode = InkCanvasEditingMode.None;
                    Cursor = Cursors.Hand;
                    break;
                case ToolMode.Pen:
                    Ink.EditingMode = InkCanvasEditingMode.Ink;
                    Cursor = Cursors.Arrow;
                    break;
                case ToolMode.Eraser:
                    Ink.EditingMode = InkCanvasEditingMode.EraseByPoint;
                    Cursor = Cursors.Arrow;
                    break;
            }
        }

        private void MoveBtn_Click(object sender, RoutedEventArgs e)
        {
            if (_currentMode != ToolMode.Move) SetMode(ToolMode.Move);
            else MoveBtn.IsChecked = true;
        }

        private void PenBtn_Click(object sender, RoutedEventArgs e)
        {
            if (_currentMode == ToolMode.Pen)
            {
                var dlg = new PenSettingsWindow(Ink.DefaultDrawingAttributes.Color, userPenWidth);
                if (dlg.ShowDialog() == true)
                {
                    Ink.DefaultDrawingAttributes.Color = dlg.SelectedColor;
                    userPenWidth = dlg.SelectedWidth;
                    UpdatePenAttributes();
                }
                PenBtn.IsChecked = true;
            }
            else
            {
                SetMode(ToolMode.Pen);
            }
        }

        private void EraserBtn_Click(object sender, RoutedEventArgs e)
        {
            if (_currentMode != ToolMode.Eraser) SetMode(ToolMode.Eraser);
            else EraserBtn.IsChecked = true;
        }

        // =========================
        // 照片面板
        // =========================
        private void TogglePhotoPanel_Click(object sender, RoutedEventArgs e)
        {
            PhotoPopup.IsOpen = !PhotoPopup.IsOpen;
        }

        private void PhotoList_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (PhotoList.SelectedItem is CapturedImage img)
            {
                _isLiveMode = false;
                _currentPhoto = img;
                VideoImage.Source = img.Image;

                // 重新订阅新 StrokeCollection 的事件，避免撤销失效
                Ink.Strokes.StrokesChanged -= Ink_StrokesChanged;
                Ink.Strokes = img.Strokes;
                Ink.Strokes.StrokesChanged += Ink_StrokesChanged;

                editHistory.Clear();
            }
        }

        private void BackToLive_Click(object sender, RoutedEventArgs e)
        {
            _isLiveMode = true;
            _currentPhoto = null;
            Ink.Strokes.Clear();
            editHistory.Clear();
        }

        private async void ShowPhotoTip()
        {
            PhotoTipPopup.IsOpen = true;
            await Task.Delay(3000);
            PhotoTipPopup.IsOpen = false;
        }

        // =========================
        // 缩放/平移
        // =========================
        private void Window_MouseWheel(object sender, MouseWheelEventArgs e)
        {
            if (_currentMode == ToolMode.Move || _currentMode == ToolMode.Pen)
            {
                double zoom = e.Delta > 0 ? 1.1 : 0.9;
                currentZoom *= zoom;
                ZoomTransform.ScaleX = currentZoom;
                ZoomTransform.ScaleY = currentZoom;
                UpdatePenAttributes();
            }
        }

        private void VideoArea_ManipulationStarting(object sender, ManipulationStartingEventArgs e)
        {
            if (_currentMode == ToolMode.Move || _currentMode == ToolMode.Pen)
            {
                e.ManipulationContainer = this;
                e.Mode = ManipulationModes.Scale | ManipulationModes.Translate;
            }
            else
            {
                e.Mode = ManipulationModes.None;
            }
        }

        private void VideoArea_ManipulationDelta(object sender, ManipulationDeltaEventArgs e)
        {
            if (!(_currentMode == ToolMode.Move || _currentMode == ToolMode.Pen))
                return;

            var delta = e.DeltaManipulation;
            currentZoom *= delta.Scale.X;
            ZoomTransform.ScaleX = currentZoom;
            ZoomTransform.ScaleY = currentZoom;
            PanTransform.X += delta.Translation.X;
            PanTransform.Y += delta.Translation.Y;
            UpdatePenAttributes();

            e.Handled = true;
        }

        private void VideoArea_MouseDown(object sender, MouseButtonEventArgs e)
        {
            if (_currentMode == ToolMode.Move || _currentMode == ToolMode.Pen)
            {
                var p = e.GetPosition(this);
                _lastMousePos = new D.Point((int)p.X, (int)p.Y);
                _isPanning = true;
                Cursor = Cursors.Hand;
            }
        }

        private void VideoArea_MouseMove(object sender, System.Windows.Input.MouseEventArgs e)
        {
            if (_isPanning && e.LeftButton == MouseButtonState.Pressed)
            {
                var pos = e.GetPosition(this);
                PanTransform.X += pos.X - _lastMousePos.X;
                PanTransform.Y += pos.Y - _lastMousePos.Y;
                _lastMousePos = new D.Point((int)pos.X, (int)pos.Y);
            }
        }

        private void VideoArea_MouseUp(object sender, MouseButtonEventArgs e)
        {
            _isPanning = false;
            Cursor = Cursors.Arrow;
        }

        // =========================
        // 按钮功能
        // =========================
        private void Capture_Click(object sender, RoutedEventArgs e)
        {
            var bmp = _videoService.GetFrameCopy();
            if (bmp != null)
            {
                D.Bitmap? processedBmp = null;
                try
                {
                    // 按当前“透视校正 + 调节”处理后再拍照保存到列表
                    processedBmp = ProcessFrame(bmp, applyAdjustments: true);

                    var img = BitmapToBitmapImage(processedBmp);
                    var photo = new CapturedImage(img);
                    _photos.Insert(0, photo);
                    _currentPhoto = photo;

                    // 显示提示
                    ShowPhotoTip();
                }
                finally
                {
                    bmp.Dispose();
                    processedBmp?.Dispose();
                }
            }
        }

        private void SaveImage_Click(object sender, RoutedEventArgs e)
        {
            if (_currentPhoto == null)
            {
                MessageBox.Show("请先拍照或选择一张图片。");
                return;
            }

            var dlg = new WinForms.SaveFileDialog
            {
                Filter = "PNG 图片|*.png|JPEG 图片|*.jpg",
                FileName = $"Capture_{DateTime.Now:yyyyMMdd_HHmmss}.png"
            };

            if (dlg.ShowDialog() == WinForms.DialogResult.OK)
            {
                SaveBitmapSourceToFile(_currentPhoto.Image, dlg.FileName);
                MessageBox.Show("保存成功！");
            }
        }

        private void ClearInk_Click(object sender, RoutedEventArgs e)
        {
            Ink.Strokes.Clear();
            editHistory.Clear();
        }

        private void UndoInk_Click(object sender, RoutedEventArgs e)
        {
            if (editHistory.Count == 0) return;

            var lastAction = editHistory.Pop();

            foreach (var stroke in lastAction.AddedStrokes)
            {
                if (Ink.Strokes.Contains(stroke))
                    Ink.Strokes.Remove(stroke);
            }

            foreach (var stroke in lastAction.RemovedStrokes)
            {
                if (!Ink.Strokes.Contains(stroke))
                    Ink.Strokes.Add(stroke);
            }
        }

        private void Minimize_Click(object sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;

        private void Exit_Click(object sender, RoutedEventArgs e)
        {
            if (MessageBox.Show("确认退出？", "退出", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
                Close();
        }

        // =========================
        // 梯形校正功能
        // =========================
        private void OpenPerspectiveCorrection_Click(object sender, RoutedEventArgs e)
        {
            var wnd = new Views.RealTimePerspectiveCorrectionWindow(_videoService);
            wnd.Owner = this;
            if (wnd.ShowDialog() == true && wnd.CorrectionPoints != null)
            {
                // 创建透视变换过滤器（要求 List<AForge.IntPoint> + 源尺寸）
                _perspectiveCorrectionFilter = new QuadrilateralTransformation(
                    wnd.CorrectionPoints,
                    wnd.SourceWidth,
                    wnd.SourceHeight);

                // 立即应用校正到直播（下一帧自动生效，此处无需强制刷新）
            }
        }

        private void ClearCorrection_Click(object sender, RoutedEventArgs e)
        {
            _perspectiveCorrectionFilter = null;

            // 刷新视频显示
            var frame = _videoService.GetFrameCopy();
            if (frame != null)
            {
                using var processed = ProcessFrame(frame, applyAdjustments: true);
                VideoImage.Source = BitmapToBitmapImage(processed);
            }
        }

        // =========================
        // 画面调节窗口（不写入 config）
        // =========================
        private void OpenAdjustVideo_Click(object sender, RoutedEventArgs e)
        {
            var wnd = new AdjustVideoWindow(
                _brightness,
                _contrast,
                _rotation,
                _mirrorHorizontal,
                _mirrorVertical
            );

            wnd.Owner = this;
            if (wnd.ShowDialog() == true)
            {
                _brightness = wnd.Brightness;
                _contrast = wnd.Contrast;
                _rotation = wnd.Rotation;
                _mirrorHorizontal = wnd.MirrorH;
                _mirrorVertical = wnd.MirrorV;
            }
        }

        // =========================
        // 摄像头切换
        // =========================
        private void SwitchCamera_Click(object sender, RoutedEventArgs e)
        {
            // 清除透视校正（新摄像头可能不同）
            _perspectiveCorrectionFilter = null;

            var cameras = _videoService.GetAvailableCameras();
            if (cameras.Count == 0)
            {
                MessageBox.Show("未找到可用摄像头。", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
                return;
            }

            var dlg = new WinForms.Form
            {
                Text = "选择摄像头",
                Width = 400,
                Height = 200,
                StartPosition = WinForms.FormStartPosition.CenterParent
            };
            var combo = new WinForms.ComboBox { Dock = WinForms.DockStyle.Top, DropDownStyle = WinForms.ComboBoxStyle.DropDownList };
            combo.Items.AddRange(cameras.ToArray());
            combo.SelectedIndex = currentCameraIndex;
            var okBtn = new WinForms.Button { Text = "确定", Dock = WinForms.DockStyle.Bottom, DialogResult = WinForms.DialogResult.OK };
            dlg.Controls.Add(combo);
            dlg.Controls.Add(okBtn);

            if (dlg.ShowDialog() == WinForms.DialogResult.OK)
            {
                currentCameraIndex = combo.SelectedIndex;
                _videoService.Stop();
                if (!_videoService.Start(currentCameraIndex))
                {
                    MessageBox.Show("切换摄像头失败。", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
                }
            }
        }

        // =========================
        // 配置保存/加载（摄像头索引 + 透视校正）
        // =========================
        private void LoadConfig()
        {
            try
            {
                if (!File.Exists(configPath)) return;

                var json = File.ReadAllText(configPath, Encoding.UTF8);
                var cfg = JsonConvert.DeserializeObject<AppConfig>(json);
                if (cfg == null) return;

                currentCameraIndex = cfg.CameraIndex;

                if (cfg.CorrectionPoints != null && cfg.CorrectionPoints.Count == 4)
                {
                    _perspectiveCorrectionFilter = new QuadrilateralTransformation(
                        cfg.CorrectionPoints, cfg.SourceWidth, cfg.SourceHeight);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("加载配置失败: " + ex.Message);
            }
        }

        private void SaveConfig()
        {
            try
            {
                var cfg = new AppConfig
                {
                    CameraIndex = currentCameraIndex
                };

                if (_perspectiveCorrectionFilter != null)
                {
                    // 保存校正点与目标尺寸
                    cfg.CorrectionPoints = new List<IntPoint>(_perspectiveCorrectionFilter.SourceQuadrilateral);
                    cfg.SourceWidth = _perspectiveCorrectionFilter.NewWidth;
                    cfg.SourceHeight = _perspectiveCorrectionFilter.NewHeight;
                }

                var json = JsonConvert.SerializeObject(cfg, Formatting.Indented);
                File.WriteAllText(configPath, json, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Console.WriteLine("保存配置失败: " + ex.Message);
            }
        }

        // =========================
        // 视频帧统一处理：校正 + 调节
        // =========================
        private D.Bitmap ProcessFrame(D.Bitmap src, bool applyAdjustments)
        {
            D.Bitmap work = src;

            try
            {
                // 1) 透视校正
                if (_perspectiveCorrectionFilter != null)
                {
                    var corrected = _perspectiveCorrectionFilter.Apply(work);
                    if (!ReferenceEquals(work, src)) work.Dispose();
                    work = corrected;
                }

                if (!applyAdjustments)
                    return work; // 返回，调用方负责 Dispose

                // 2) 亮度/对比度（-100~100）
                if (Math.Abs(_brightness) > 0.01)
                {
                    var bc = new BrightnessCorrection((int)Math.Max(-100, Math.Min(100, _brightness)));
                    bc.ApplyInPlace(work);
                }
                if (Math.Abs(_contrast) > 0.01)
                {
                    var cc = new ContrastCorrection((int)Math.Max(-100, Math.Min(100, _contrast)));
                    cc.ApplyInPlace(work);
                }

                // 3) 旋转（使用 System.Drawing 原生，避免 AForge 额外复制）
                if (_rotation == 90) work.RotateFlip(D.RotateFlipType.Rotate90FlipNone);
                else if (_rotation == 180) work.RotateFlip(D.RotateFlipType.Rotate180FlipNone);
                else if (_rotation == 270) work.RotateFlip(D.RotateFlipType.Rotate270FlipNone);

                // 4) 镜像
                if (_mirrorHorizontal) work.RotateFlip(D.RotateFlipType.RotateNoneFlipX);
                if (_mirrorVertical) work.RotateFlip(D.RotateFlipType.RotateNoneFlipY);

                return work;
            }
            catch
            {
                // 出错回退到原图
                if (!ReferenceEquals(work, src)) work.Dispose();
                return src;
            }
        }

        // =========================
        // 工具方法
        // =========================
        private BitmapImage BitmapToBitmapImage(D.Bitmap bitmap)
        {
            using var memory = new MemoryStream();
            bitmap.Save(memory, D.Imaging.ImageFormat.Bmp);
            memory.Position = 0;
            var bmpImage = new BitmapImage();
            bmpImage.BeginInit();
            bmpImage.StreamSource = memory;
            bmpImage.CacheOption = BitmapCacheOption.OnLoad;
            bmpImage.EndInit();
            bmpImage.Freeze();
            return bmpImage;
        }

        private void SaveBitmapSourceToFile(BitmapSource bitmap, string filePath)
        {
            BitmapEncoder encoder = filePath.EndsWith(".jpg", StringComparison.OrdinalIgnoreCase)
                ? new JpegBitmapEncoder()
                : new PngBitmapEncoder();
            encoder.Frames.Add(BitmapFrame.Create(bitmap));
            using var stream = new FileStream(filePath, FileMode.Create);
            encoder.Save(stream);
        }

        protected override void OnClosed(EventArgs e)
        {
            SaveConfig();
            _videoService.Dispose();
            base.OnClosed(e);
        }
    }
}

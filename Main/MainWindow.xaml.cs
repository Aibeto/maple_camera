using AForge;
using AForge.Imaging.Filters;
using Newtonsoft.Json;
using ShowWrite.Models;
using ShowWrite.Services;
using ShowWrite.Views;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Ink;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using ZXing;
using ZXing.Common;
using ZXing.QrCode;
using Cursors = System.Windows.Input.Cursors;
using D = System.Drawing;
using MessageBox = System.Windows.MessageBox;
using WinForms = System.Windows.Forms;

namespace ShowWrite
{
    public partial class MainWindow : Window
    {
        private readonly VideoService _videoService = new();
        private readonly ObservableCollection<CapturedImage> _photos = new();
        private CapturedImage? _currentPhoto;
        private bool _isLiveMode = true;
        private int currentCameraIndex = 0;
        
        // 透视校正过滤器
        private QuadrilateralTransformation? _perspectiveCorrectionFilter;
        
        // 配置对象
        private AppConfig config = new AppConfig();
        
        private enum ToolMode { None, Move, Pen, Eraser }
        private ToolMode _currentMode = ToolMode.None;
        private D.Point _lastMousePos;
        private bool _isPanning = false;
        
        // 缩放比例 & 用户笔宽
        private double currentZoom = 1.0;
        private double userPenWidth = 2.0;
        
        // 编辑历史
        private readonly Stack<EditAction> editHistory = new Stack<EditAction>();
        private EditAction? currentEdit = null;
        private bool isEditing = false;
        
        private class EditAction
        {
            public List<Stroke> AddedStrokes { get; } = new();
            public List<Stroke> RemovedStrokes { get; } = new();
        }
        
        // 画面调节参数
        private double _brightness = 0.0;
        private double _contrast = 0.0;
        private int _rotation = 0;
        private bool _mirrorHorizontal = false;
        private bool _mirrorVertical = false;
        
        // 配置文件路径
        private readonly string configPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "config.json");
        
        // 触摸点跟踪
        private readonly Dictionary<int, System.Windows.Point> _touchPoints = new Dictionary<int, System.Windows.Point>();
        private double _lastTouchDistance = -1;
        private System.Windows.Point _lastTouchCenter;

        public MainWindow()
        {
            InitializeComponent();
            PhotoList.ItemsSource = _photos;
            
            // 加载配置
            LoadConfig();
            
            // 应用窗口设置
            WindowStyle = WindowStyle.None;
            WindowState = config.StartMaximized ? WindowState.Maximized : WindowState.Normal;
            
            // 应用画笔设置
            var penColor = (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString(config.DefaultPenColor);
            Ink.DefaultDrawingAttributes.Color = penColor;
            userPenWidth = config.DefaultPenWidth;
            
            // 捕捉画笔/橡皮事件
            Ink.StrokeCollected += Ink_StrokeCollected;
            Ink.PreviewMouseLeftButtonDown += Ink_PreviewMouseDown;
            Ink.PreviewMouseLeftButtonUp += Ink_PreviewMouseUp;
            Ink.PreviewStylusDown += Ink_PreviewStylusDown;
            Ink.PreviewStylusUp += Ink_PreviewStylusUp;
            Ink.EraserShape = new RectangleStylusShape(20, 20);
            
            // 仅用于橡皮
            Ink.Strokes.StrokesChanged += Ink_StrokesChanged;
            
            SetMode(ToolMode.Move, initial: true);
            
            _videoService.OnNewFrameProcessed += frame =>
            {
                Dispatcher.Invoke(() =>
                {
                    if (_isLiveMode)
                    {
                        using var processed = ProcessFrame((D.Bitmap)frame.Clone(), applyAdjustments: true);
                        VideoImage.Source = BitmapToBitmapImage(processed);
                    }
                });
            };
            
            // 如果配置为自动启动摄像头，则尝试启动
            if (config.AutoStartCamera && !_videoService.Start(currentCameraIndex))
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
        // 编辑操作管理
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
            if (_currentMode == ToolMode.Pen) return;
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
            
            // 重置触摸状态
            _touchPoints.Clear();
            _lastTouchDistance = -1;
            
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
                // 获取当前橡皮擦大小（从 Ink.EraserShape）
                double currentEraserWidth = ((RectangleStylusShape)Ink.EraserShape).Width;

                var dlg = new PenSettingsWindow(Ink.DefaultDrawingAttributes.Color, userPenWidth, currentEraserWidth);
                if (dlg.ShowDialog() == true)
                {
                    Ink.DefaultDrawingAttributes.Color = dlg.SelectedColor;
                    userPenWidth = dlg.SelectedPenWidth;

                    // 更新橡皮擦大小
                    Ink.EraserShape = new RectangleStylusShape(dlg.SelectedEraserWidth, dlg.SelectedEraserWidth);

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
            // 如果橡皮擦已经是选中状态，则执行清屏操作
            if (_currentMode == ToolMode.Eraser)
            {
                // 显示确认对话框
                if (MessageBox.Show("确定要清除所有笔迹吗？", "清屏确认", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
                {
                    ClearInk_Click(sender, e);
                }
                // 保持橡皮擦按钮的选中状态
                EraserBtn.IsChecked = true;
            }
            else
            {
                // 否则切换到橡皮擦模式
                SetMode(ToolMode.Eraser);
            }
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
        // 缩放/平移（以鼠标为中心）
        // =========================
        private void Window_MouseWheel(object sender, MouseWheelEventArgs e)
        {
            if (_currentMode == ToolMode.Move || _currentMode == ToolMode.Pen)
            {
                // 获取鼠标相对于VideoArea的位置
                System.Windows.Point mousePos = e.GetPosition(VideoArea);
                
                // 计算缩放因子
                double zoomFactor = e.Delta > 0 ? 1.1 : 0.9;
                double newZoom = currentZoom * zoomFactor;
                
                // 限制缩放范围
                newZoom = Math.Max(0.1, Math.Min(10, newZoom));
                
                // 计算缩放中心相对于当前变换的位置
                System.Windows.Point relative = new System.Windows.Point(
                    (mousePos.X - PanTransform.X) / currentZoom,
                    (mousePos.Y - PanTransform.Y) / currentZoom);
                
                // 应用缩放
                currentZoom = newZoom;
                ZoomTransform.ScaleX = currentZoom;
                ZoomTransform.ScaleY = currentZoom;
                
                // 调整平移以使缩放中心保持不变
                PanTransform.X = mousePos.X - relative.X * currentZoom;
                PanTransform.Y = mousePos.Y - relative.Y * currentZoom;
                
                UpdatePenAttributes();
            }
        }
        
        private void VideoArea_ManipulationStarting(object sender, ManipulationStartingEventArgs e)
        {
            // 只在移动模式下启用手势操作
            if (_currentMode == ToolMode.Move)
            {
                e.ManipulationContainer = this;
                e.Mode = ManipulationModes.Scale | ManipulationModes.Translate;
            }
            // 在画笔和橡皮擦模式下，只启用手势检测但不自动处理
            else if (_currentMode == ToolMode.Pen || _currentMode == ToolMode.Eraser)
            {
                e.ManipulationContainer = this;
                e.Mode = ManipulationModes.All;
                e.Handled = true; // 标记为已处理，防止系统自动处理
            }
            else
            {
                e.Mode = ManipulationModes.None;
            }
        }
        
        private void VideoArea_ManipulationDelta(object sender, ManipulationDeltaEventArgs e)
        {
            // 只在移动模式下处理手势
            if (_currentMode != ToolMode.Move)
                return;
            
            var delta = e.DeltaManipulation;
            
            // 处理缩放（以手势中心为中心）
            if (delta.Scale.X != 1.0 || delta.Scale.Y != 1.0)
            {
                // 获取手势中心相对于VideoArea的位置
                System.Windows.Point center = e.ManipulationOrigin;
                System.Windows.Point relativeCenter = VideoArea.TranslatePoint(center, this);
                
                // 计算缩放前的相对位置
                System.Windows.Point relative = new System.Windows.Point(
                    (relativeCenter.X - PanTransform.X) / currentZoom,
                    (relativeCenter.Y - PanTransform.Y) / currentZoom);
                
                // 应用缩放
                currentZoom *= delta.Scale.X;
                currentZoom = Math.Max(0.1, Math.Min(10, currentZoom));
                ZoomTransform.ScaleX = currentZoom;
                ZoomTransform.ScaleY = currentZoom;
                
                // 调整平移以使缩放中心保持不变
                PanTransform.X = relativeCenter.X - relative.X * currentZoom;
                PanTransform.Y = relativeCenter.Y - relative.Y * currentZoom;
            }
            
            // 处理平移
            PanTransform.X += delta.Translation.X;
            PanTransform.Y += delta.Translation.Y;
            
            UpdatePenAttributes();
            e.Handled = true;
        }
        
        private void VideoArea_MouseDown(object sender, MouseButtonEventArgs e)
        {
            // 只在移动模式下启用平移
            if (_currentMode == ToolMode.Move)
            {
                var p = e.GetPosition(this);
                _lastMousePos = new D.Point((int)p.X, (int)p.Y);
                _isPanning = true;
                Cursor = Cursors.Hand;
            }
        }
        
        private void VideoArea_MouseMove(object sender, System.Windows.Input.MouseEventArgs e)
        {
            // 只在移动模式下处理平移
            if (_isPanning && _currentMode == ToolMode.Move && e.LeftButton == MouseButtonState.Pressed)
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
        // 触摸事件处理
        // =========================
        protected override void OnTouchDown(TouchEventArgs e)
        {
            base.OnTouchDown(e);

            // 记录触摸点
            var touchPoint = e.GetTouchPoint(VideoArea);
            _touchPoints[e.TouchDevice.Id] = touchPoint.Position;

            // 更新触摸中心点和距离
            UpdateTouchCenterAndDistance();

            // 只在移动模式下处理手势
            if (_currentMode == ToolMode.Move)
            {
                e.Handled = true;
            }
            else
            {
                e.Handled = false; // 允许事件继续传递到 InkCanvas
            }
        }

        protected override void OnTouchMove(TouchEventArgs e)
        {
            base.OnTouchMove(e);

            // 更新触摸点位置
            if (_touchPoints.ContainsKey(e.TouchDevice.Id))
            {
                var touchPoint = e.GetTouchPoint(VideoArea);
                _touchPoints[e.TouchDevice.Id] = touchPoint.Position;

                // 更新触摸中心点和距离
                UpdateTouchCenterAndDistance();

                // 只在移动模式下处理手势
                if (_currentMode == ToolMode.Move && _touchPoints.Count >= 2)
                {
                    HandleMultiTouchGesture();
                    e.Handled = true;
                }
                else
                {
                    e.Handled = false; // 允许事件继续传递到 InkCanvas
                }
            }
        }

        protected override void OnTouchUp(TouchEventArgs e)
        {
            base.OnTouchUp(e);

            // 移除触摸点
            if (_touchPoints.ContainsKey(e.TouchDevice.Id))
            {
                _touchPoints.Remove(e.TouchDevice.Id);

                // 更新触摸中心点和距离
                UpdateTouchCenterAndDistance();

                // 重置最后触摸距离
                if (_touchPoints.Count < 2)
                {
                    _lastTouchDistance = -1;
                }
            }

            // 只在移动模式下处理手势
            e.Handled = (_currentMode == ToolMode.Move);
        }

        // 更新触摸中心点和距离
        private void UpdateTouchCenterAndDistance()
        {
            if (_touchPoints.Count == 0)
            {
                _lastTouchCenter = new System.Windows.Point(0, 0);
                _lastTouchDistance = -1;
                return;
            }
            
            // 计算中心点
            double centerX = 0, centerY = 0;
            foreach (var point in _touchPoints.Values)
            {
                centerX += point.X;
                centerY += point.Y;
            }
            centerX /= _touchPoints.Count;
            centerY /= _touchPoints.Count;
            _lastTouchCenter = new System.Windows.Point(centerX, centerY);
            
            // 计算两点之间的距离（如果是双指）
            if (_touchPoints.Count == 2)
            {
                var points = _touchPoints.Values.ToArray();
                double dx = points[1].X - points[0].X;
                double dy = points[1].Y - points[0].Y;
                _lastTouchDistance = Math.Sqrt(dx * dx + dy * dy);
            }
            else
            {
                _lastTouchDistance = -1;
            }
        }
        
        // 处理多指手势（缩放和平移）
        private void HandleMultiTouchGesture()
        {
            if (_touchPoints.Count < 2 || _lastTouchDistance <= 0)
                return;
            
            // 计算当前两点之间的距离
            var points = _touchPoints.Values.ToArray();
            double dx = points[1].X - points[0].X;
            double dy = points[1].Y - points[0].Y;
            double currentDistance = Math.Sqrt(dx * dx + dy * dy);
            
            // 计算缩放比例
            if (_lastTouchDistance > 0)
            {
                double scaleFactor = currentDistance / _lastTouchDistance;
                double newZoom = currentZoom * scaleFactor;
                
                // 限制缩放范围
                newZoom = Math.Max(0.1, Math.Min(10, newZoom));
                
                // 计算缩放中心相对于当前变换的位置
                System.Windows.Point relative = new System.Windows.Point(
                    (_lastTouchCenter.X - PanTransform.X) / currentZoom,
                    (_lastTouchCenter.Y - PanTransform.Y) / currentZoom);
                
                // 应用缩放
                currentZoom = newZoom;
                ZoomTransform.ScaleX = currentZoom;
                ZoomTransform.ScaleY = currentZoom;
                
                // 调整平移以使缩放中心保持不变
                PanTransform.X = _lastTouchCenter.X - relative.X * currentZoom;
                PanTransform.Y = _lastTouchCenter.Y - relative.Y * currentZoom;
                
                UpdatePenAttributes();
            }
            
            // 更新最后触摸距离
            _lastTouchDistance = currentDistance;
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
                _perspectiveCorrectionFilter = new QuadrilateralTransformation(
                    wnd.CorrectionPoints,
                    wnd.SourceWidth,
                    wnd.SourceHeight);
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
        
        private void VideoArea_MouseDoubleClick(object sender, MouseButtonEventArgs e)
        {
            if (_currentMode == ToolMode.Move)
            {
                try
                {
                    _videoService.AutoFocus();
                    MessageBox.Show("已触发自动对焦。", "对焦");
                }
                catch (Exception ex)
                {
                    MessageBox.Show("自动对焦失败: " + ex.Message, "错误");
                }
            }
        }
        
        // 从 Bitmap 构建 ZXing 的 BinaryBitmap 并解码
        private ZXing.Result? DecodeBarcodeFromBitmap(D.Bitmap src)
        {
            using var bmp24 = new D.Bitmap(src.Width, src.Height, D.Imaging.PixelFormat.Format24bppRgb);
            using (var g = D.Graphics.FromImage(bmp24))
            {
                g.DrawImage(src, 0, 0, bmp24.Width, bmp24.Height);
            }
            
            var rect = new D.Rectangle(0, 0, bmp24.Width, bmp24.Height);
            var data = bmp24.LockBits(rect, ImageLockMode.ReadOnly, D.Imaging.PixelFormat.Format24bppRgb);
            
            try
            {
                int stride = Math.Abs(data.Stride);
                int length = stride * bmp24.Height;
                byte[] buffer = new byte[length];
                Marshal.Copy(data.Scan0, buffer, 0, length);
                
                var luminance = new RGBLuminanceSource(buffer, bmp24.Width, bmp24.Height, RGBLuminanceSource.BitmapFormat.BGR24);
                var binary = new BinaryBitmap(new HybridBinarizer(luminance));
                
                var reader = new MultiFormatReader();
                var hints = new Dictionary<DecodeHintType, object>
                {
                    { DecodeHintType.TRY_HARDER, true },
                    { DecodeHintType.POSSIBLE_FORMATS, new[]
                        {
                            BarcodeFormat.QR_CODE, BarcodeFormat.DATA_MATRIX, BarcodeFormat.AZTEC,
                            BarcodeFormat.PDF_417, BarcodeFormat.CODE_128, BarcodeFormat.CODE_39,
                            BarcodeFormat.EAN_13, BarcodeFormat.EAN_8, BarcodeFormat.UPC_A
                        }
                    }
                };
                
                return reader.decode(binary, hints);
            }
            catch (ReaderException)
            {
                return null;
            }
            finally
            {
                bmp24.UnlockBits(data);
            }
        }
        
        // "扫一扫"点击事件
        private void ScanQRCode_Click(object sender, RoutedEventArgs e)
        {
            var frame = _videoService.GetFrameCopy();
            if (frame == null) return;
            
            D.Bitmap? corrected = null;
            try
            {
                var target = frame;
                if (_perspectiveCorrectionFilter != null)
                {
                    corrected = _perspectiveCorrectionFilter.Apply(frame);
                    target = corrected;
                }
                
                var result = DecodeBarcodeFromBitmap(target);
                if (result != null)
                {
                    System.Windows.Clipboard.SetText(result.Text ?? string.Empty);
                    MessageBox.Show($"识别到：{result.BarcodeFormat}\n{result.Text}\n(已复制到剪贴板)", "扫一扫");
                }
                else
                {
                    MessageBox.Show("未检测到二维码/条码。", "扫一扫");
                }
            }
            finally
            {
                corrected?.Dispose();
                frame.Dispose();
            }
        }
        
        private void ScanDocument_Click(object sender, RoutedEventArgs e)
        {
            var bmp = _videoService.GetFrameCopy();
            if (bmp == null) return;
            
            D.Bitmap? processed = null;
            try
            {
                processed = ProcessFrame(bmp, applyAdjustments: true);
                
                var gray = AForge.Imaging.Filters.Grayscale.CommonAlgorithms.BT709.Apply(processed);
                
                var threshold = new AForge.Imaging.Filters.BradleyLocalThresholding
                {
                    WindowSize = 41,
                    PixelBrightnessDifferenceLimit = 0.1f
                };
                threshold.ApplyInPlace(gray);
                
                var img = BitmapToBitmapImage(gray);
                var photo = new CapturedImage(img);
                _photos.Insert(0, photo);
                _currentPhoto = photo;
                
                ShowPhotoTip();
            }
            finally
            {
                bmp.Dispose();
                processed?.Dispose();
            }
        }
        
        // =========================
        // 画面调节窗口
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
        // 配置保存/加载
        // =========================
        private void LoadConfig()
        {
            try
            {
                if (!File.Exists(configPath))
                {
                    config = new AppConfig();
                    return;
                }
                
                var json = File.ReadAllText(configPath, Encoding.UTF8);
                var cfg = JsonConvert.DeserializeObject<AppConfig>(json);
                
                if (cfg == null)
                {
                    config = new AppConfig();
                    return;
                }
                
                currentCameraIndex = cfg.CameraIndex;
                config = cfg;
                
                // 加载梯形校正数据
                if (cfg.CorrectionPoints != null && cfg.CorrectionPoints.Count == 4)
                {
                    _perspectiveCorrectionFilter = new QuadrilateralTransformation(
                        cfg.CorrectionPoints, cfg.SourceWidth, cfg.SourceHeight);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("加载配置失败: " + ex.Message);
                config = new AppConfig();
            }
        }
        
        private void SaveConfig()
        {
            try
            {
                var cfg = new AppConfig
                {
                    CameraIndex = currentCameraIndex,
                    CorrectionPoints = _perspectiveCorrectionFilter != null ?
                        new List<IntPoint>(_perspectiveCorrectionFilter.SourceQuadrilateral) : null,
                    SourceWidth = _perspectiveCorrectionFilter?.NewWidth ?? 0,
                    SourceHeight = _perspectiveCorrectionFilter?.NewHeight ?? 0,
                    StartMaximized = config.StartMaximized,
                    AutoStartCamera = config.AutoStartCamera,
                    DefaultPenWidth = userPenWidth,
                    DefaultPenColor = Ink.DefaultDrawingAttributes.Color.ToString(),
                    EnableHardwareAcceleration = config.EnableHardwareAcceleration,
                    FrameRateLimit = config.FrameRateLimit
                };
                
                var json = JsonConvert.SerializeObject(cfg, Formatting.Indented);
                File.WriteAllText(configPath, json, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Console.WriteLine("保存配置失败: " + ex.Message);
            }
        }
        
        // =========================
        // 设置窗口功能
        // =========================
        private void OpenSettings_Click(object sender, RoutedEventArgs e)
        {
            var cameras = _videoService.GetAvailableCameras();
            
            var settingsWindow = new SettingsWindow(config, cameras)
            {
                Owner = this,
                WindowStartupLocation = WindowStartupLocation.CenterOwner
            };
            
            if (settingsWindow.ShowDialog() == true)
            {
                WindowState = config.StartMaximized ? WindowState.Maximized : WindowState.Normal;
                
                var penColor = (System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString(config.DefaultPenColor);
                Ink.DefaultDrawingAttributes.Color = penColor;
                userPenWidth = config.DefaultPenWidth;
                UpdatePenAttributes();
                
                SaveConfig();
                
                if (currentCameraIndex != config.CameraIndex)
                {
                    currentCameraIndex = config.CameraIndex;
                    _videoService.Stop();
                    if (config.AutoStartCamera && !_videoService.Start(currentCameraIndex))
                    {
                        MessageBox.Show("切换摄像头失败。", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
                    }
                }
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
                    return work;
                
                // 2) 亮度/对比度
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
                
                // 3) 旋转
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
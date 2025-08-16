using System;
using System.Collections.ObjectModel;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Ink;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using WinForms = System.Windows.Forms;
using ShowWrite.Models;
using ShowWrite.Services;
using D = System.Drawing;
using ImageMagick;
using MessageBox = System.Windows.MessageBox;
using Cursors = System.Windows.Input.Cursors;

namespace ShowWrite
{
    public partial class MainWindow : Window
    {
        private readonly VideoService _videoService = new();
        private readonly ObservableCollection<CapturedImage> _photos = new();
        private CapturedImage? _currentPhoto;
        private bool _isLiveMode = true;

        private enum ToolMode { None, Move, Pen, Eraser }
        private ToolMode _currentMode = ToolMode.None;

        private D.Point _lastMousePos;
        private bool _isPanning = false;

        // 新增：缩放比例 & 用户笔宽
        private double currentZoom = 1.0;
        private double userPenWidth = 2.0;

        public MainWindow()
        {
            InitializeComponent();
            PhotoList.ItemsSource = _photos;

            WindowStyle = WindowStyle.None;
            WindowState = WindowState.Maximized;

            SetMode(ToolMode.Pen, initial: true);

            _videoService.OnNewFrameProcessed += frame =>
            {
                if (_isLiveMode)
                {
                    Dispatcher.Invoke(() =>
                    {
                        VideoImage.Source = BitmapToBitmapImage(frame);
                    });
                }
            };

            if (!_videoService.Start(0))
            {
                MessageBox.Show("未找到可用摄像头。", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
            }

            UpdatePenAttributes();
        }

        private void UpdatePenAttributes()
        {
            Ink.DefaultDrawingAttributes.Width = userPenWidth / currentZoom;
            Ink.DefaultDrawingAttributes.Height = userPenWidth / currentZoom;
        }

        #region 模式切换
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
        #endregion

        #region 照片窗口与提示
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
                Ink.Strokes = img.Strokes;
            }
        }

        private void BackToLive_Click(object sender, RoutedEventArgs e)
        {
            _isLiveMode = true;
            _currentPhoto = null;
            Ink.Strokes.Clear();
        }

        private async void ShowPhotoTip()
        {
            PhotoTipPopup.IsOpen = true;
            await Task.Delay(3000);
            PhotoTipPopup.IsOpen = false;
        }
        #endregion

        #region 缩放与平移
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
        #endregion

        #region 按钮功能
        private void Capture_Click(object sender, RoutedEventArgs e)
        {
            var bmp = _videoService.GetFrameCopy();
            if (bmp != null)
            {
                var img = BitmapToBitmapImage(bmp);
                var photo = new CapturedImage(img);
                _photos.Insert(0, photo);
                _currentPhoto = photo;
                bmp.Dispose();

                _isLiveMode = true;
                VideoImage.Source = img;
                Ink.Strokes.Clear();

                ShowPhotoTip();
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

        private void ClearInk_Click(object sender, RoutedEventArgs e) => Ink.Strokes.Clear();

        private void UndoInk_Click(object sender, RoutedEventArgs e)
        {
            if (Ink.Strokes.Count > 0) Ink.Strokes.RemoveAt(Ink.Strokes.Count - 1);
        }

        private void Minimize_Click(object sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;

        private void Exit_Click(object sender, RoutedEventArgs e)
        {
            if (MessageBox.Show("确认退出？", "退出", MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
                Close();
        }
        #endregion

        #region 工具方法
        private void OpenPerspectiveCorrection_Click(object sender, RoutedEventArgs e)
        {
            BitmapSource? src = null;

            if (_isLiveMode)
            {
                var bmp = _videoService.GetFrameCopy();
                if (bmp != null)
                {
                    src = BitmapToBitmapImage(bmp);
                    bmp.Dispose();
                }
            }
            else if (_currentPhoto != null)
            {
                src = _currentPhoto.Image;
            }

            if (src != null)
            {
                var wnd = new Views.PerspectiveCorrectionWindow(src);
                wnd.Owner = this;
                if (wnd.ShowDialog() == true && wnd.CorrectedImage != null)
                {
                    if (_isLiveMode)
                    {
                        _photos.Insert(0, new CapturedImage(wnd.CorrectedImage));
                        _currentPhoto = _photos[0];
                    }
                    else if (_currentPhoto != null)
                    {
                        _currentPhoto.Image = wnd.CorrectedImage;
                    }

                    VideoImage.Source = wnd.CorrectedImage;
                }
            }
        }

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
            _videoService.Dispose();
            base.OnClosed(e);
        }
        #endregion
    }
}

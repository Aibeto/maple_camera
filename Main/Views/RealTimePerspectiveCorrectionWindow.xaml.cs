using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using System.Drawing;
using AForge;
using AForge.Imaging.Filters;
using ShowWrite.Services;

namespace ShowWrite.Views
{
    public partial class RealTimePerspectiveCorrectionWindow : Window
    {
        private readonly List<System.Windows.Point> _points = new List<System.Windows.Point>();
        private readonly List<Ellipse> _markers = new List<Ellipse>();
        private readonly VideoService _videoService;
        private bool _isTransforming = false;
        private QuadrilateralTransformation? _transformationFilter;

        // 添加属性用于返回校正参数
        public List<IntPoint>? CorrectionPoints { get; private set; }
        public int SourceWidth { get; private set; }
        public int SourceHeight { get; private set; }

        public RealTimePerspectiveCorrectionWindow(VideoService videoService)
        {
            InitializeComponent();
            _videoService = videoService;
            _videoService.OnNewFrameProcessed += VideoService_OnNewFrameProcessed;
            Closed += (s, e) => _videoService.OnNewFrameProcessed -= VideoService_OnNewFrameProcessed;
        }

        private void VideoService_OnNewFrameProcessed(Bitmap frame)
        {
            Dispatcher.Invoke(() =>
            {
                try
                {
                    if (_isTransforming && _transformationFilter != null && _points.Count == 4)
                    {
                        // 应用透视变换
                        using (var transformed = _transformationFilter.Apply(frame))
                        {
                            PreviewImage.Source = ConvertBitmapToBitmapSource(transformed);
                        }
                    }
                    else
                    {
                        // 直接显示原始帧
                        PreviewImage.Source = ConvertBitmapToBitmapSource(frame);
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Error processing frame: {ex.Message}");
                }
            });
        }

        private BitmapImage ConvertBitmapToBitmapSource(Bitmap bitmap)
        {
            using (var memory = new System.IO.MemoryStream())
            {
                bitmap.Save(memory, System.Drawing.Imaging.ImageFormat.Bmp);
                memory.Position = 0;
                var bitmapImage = new BitmapImage();
                bitmapImage.BeginInit();
                bitmapImage.StreamSource = memory;
                bitmapImage.CacheOption = BitmapCacheOption.OnLoad;
                bitmapImage.EndInit();
                bitmapImage.Freeze();
                return bitmapImage;
            }
        }

        private void Image_MouseDown(object sender, MouseButtonEventArgs e)
        {
            if (_points.Count >= 4) return;

            var position = e.GetPosition(PreviewImage);
            _points.Add(position);

            // 添加标记
            var ellipse = new Ellipse
            {
                Width = 10,
                Height = 10,
                Fill = System.Windows.Media.Brushes.Red,
                Stroke = System.Windows.Media.Brushes.White,
                StrokeThickness = 2
            };

            Canvas.SetLeft(ellipse, position.X - 5);
            Canvas.SetTop(ellipse, position.Y - 5);
            MarkersCanvas.Children.Add(ellipse);
            _markers.Add(ellipse);

            // 当选择了4个点时，创建变换过滤器
            if (_points.Count == 4)
            {
                CreateTransformationFilter();
            }
        }

        private void CreateTransformationFilter()
        {
            try
            {
                // 获取当前帧
                using (var currentFrame = _videoService.GetFrameCopy())
                {
                    if (currentFrame == null) return;

                    // 保存原始尺寸（用于主窗口应用校正）
                    SourceWidth = currentFrame.Width;
                    SourceHeight = currentFrame.Height;

                    // 计算实际图像坐标（考虑缩放）
                    double scaleX = currentFrame.Width / PreviewImage.ActualWidth;
                    double scaleY = currentFrame.Height / PreviewImage.ActualHeight;

                    // 创建点列表（左上 -> 右上 -> 右下 -> 左下）
                    CorrectionPoints = new List<IntPoint>();
                    foreach (var point in _points)
                    {
                        CorrectionPoints.Add(new IntPoint(
                            (int)(point.X * scaleX),
                            (int)(point.Y * scaleY)));
                    }

                    // 创建透视变换过滤器
                    _transformationFilter = new QuadrilateralTransformation(
                        CorrectionPoints,
                        currentFrame.Width,
                        currentFrame.Height);

                    _isTransforming = true;
                }
            }
            catch (Exception ex)
            {
                System.Windows.MessageBox.Show($"创建变换过滤器失败: {ex.Message}", "错误",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void OK_Click(object sender, RoutedEventArgs e)
        {
            if (_points.Count == 4)
            {
                DialogResult = true;
                Close();
            }
            else
            {
                System.Windows.MessageBox.Show("请选择4个点进行梯形校正", "提示",
                    MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        private void Cancel_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }

        private void Reset_Click(object sender, RoutedEventArgs e)
        {
            _points.Clear();
            _markers.Clear();
            MarkersCanvas.Children.Clear();
            _isTransforming = false;
            _transformationFilter = null;
            CorrectionPoints = null;
        }
    }
}
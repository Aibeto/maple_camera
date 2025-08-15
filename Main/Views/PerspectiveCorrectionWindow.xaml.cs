using ImageMagick;
using System;
using System.Collections.Generic;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Media.Imaging;
using MessageBox = System.Windows.MessageBox;

namespace ShowWrite.Views
{
    public partial class PerspectiveCorrectionWindow : Window
    {
        private readonly BitmapSource _sourceImage;
        private BitmapSource? _correctedImage;

        public BitmapSource? CorrectedImage => _correctedImage;

        public PerspectiveCorrectionWindow(BitmapSource sourceImage)
        {
            InitializeComponent();
            _sourceImage = sourceImage;
            PreviewImage.Source = _sourceImage;
            Loaded += PerspectiveCorrectionWindow_Loaded;
        }

        private void PerspectiveCorrectionWindow_Loaded(object sender, RoutedEventArgs e)
        {
            // 原图像素大小
            double imgWidth = _sourceImage.PixelWidth;
            double imgHeight = _sourceImage.PixelHeight;

            PreviewImage.Width = imgWidth;
            PreviewImage.Height = imgHeight;

            // 默认四角位置
            SetThumbPosition(Point0, 20, 20);
            SetThumbPosition(Point1, imgWidth - 40, 20);
            SetThumbPosition(Point2, imgWidth - 40, imgHeight - 40);
            SetThumbPosition(Point3, 20, imgHeight - 40);
        }

        private void SetThumbPosition(Thumb thumb, double x, double y)
        {
            Canvas.SetLeft(thumb, x - thumb.Width / 2);
            Canvas.SetTop(thumb, y - thumb.Height / 2);
        }

        private System.Drawing.Point GetThumbPosition(Thumb thumb)
        {
            return new System.Drawing.Point(
                (int)(Canvas.GetLeft(thumb) + thumb.Width / 2),
                (int)(Canvas.GetTop(thumb) + thumb.Height / 2)
            );
        }

        private void Point_DragDelta(object sender, DragDeltaEventArgs e)
        {
            var thumb = (Thumb)sender;
            Canvas.SetLeft(thumb, Canvas.GetLeft(thumb) + e.HorizontalChange);
            Canvas.SetTop(thumb, Canvas.GetTop(thumb) + e.VerticalChange);
        }

        private void Correct_Click(object sender, RoutedEventArgs e)
        {
            var points = new List<System.Drawing.Point>
            {
                GetThumbPosition(Point0),
                GetThumbPosition(Point1),
                GetThumbPosition(Point2),
                GetThumbPosition(Point3)
            };

            // 转成字节流
            byte[] imageBytes;
            using (var ms = new MemoryStream())
            {
                BitmapEncoder encoder = new PngBitmapEncoder();
                encoder.Frames.Add(BitmapFrame.Create(_sourceImage));
                encoder.Save(ms);
                imageBytes = ms.ToArray();
            }

            using (var img = new MagickImage(imageBytes))
            {
                var srcPoints = new double[]
                {
                    points[0].X, points[0].Y,
                    points[1].X, points[1].Y,
                    points[2].X, points[2].Y,
                    points[3].X, points[3].Y
                };

                double width = Math.Max(Distance(points[0], points[1]),
                                        Distance(points[2], points[3]));
                double height = Math.Max(Distance(points[1], points[2]),
                                         Distance(points[3], points[0]));

                var dstPoints = new double[]
                {
                    0, 0,
                    width, 0,
                    width, height,
                    0, height
                };

                img.VirtualPixelMethod = VirtualPixelMethod.Transparent;
                img.Distort(DistortMethod.Perspective, CombineArrays(srcPoints, dstPoints));

                _correctedImage = MagickToBitmapSource(img);
                PreviewImage.Source = _correctedImage;
            }
        }

        private void SaveAndClose_Click(object sender, RoutedEventArgs e)
        {
            if (_correctedImage != null)
            {
                DialogResult = true;
                Close();
            }
            else
            {
                MessageBox.Show("请先执行校正。");
            }
        }

        private void Cancel_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }

        private double[] CombineArrays(double[] a, double[] b)
        {
            var result = new double[a.Length + b.Length];
            a.CopyTo(result, 0);
            b.CopyTo(result, a.Length);
            return result;
        }

        private double Distance(System.Drawing.Point p1, System.Drawing.Point p2)
        {
            var dx = p1.X - p2.X;
            var dy = p1.Y - p2.Y;
            return Math.Sqrt(dx * dx + dy * dy);
        }

        private BitmapSource MagickToBitmapSource(MagickImage img)
        {
            using var ms = new MemoryStream();
            img.Write(ms, MagickFormat.Png);
            ms.Position = 0;
            var bmp = new BitmapImage();
            bmp.BeginInit();
            bmp.StreamSource = ms;
            bmp.CacheOption = BitmapCacheOption.OnLoad;
            bmp.EndInit();
            bmp.Freeze();
            return bmp;
        }
    }
}

using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Shapes;

namespace ShowWrite.Views
{
    public partial class RealTimePerspectiveCorrectionWindow : Window
    {
        private readonly List<System.Windows.Point> _points = new List<System.Windows.Point>();
        private readonly List<Ellipse> _markers = new List<Ellipse>();

        public System.Windows.Point[] SelectedPoints => _points.ToArray();

        public RealTimePerspectiveCorrectionWindow()
        {
            InitializeComponent();
        }

        public void SetImageSource(ImageSource source)
        {
            PreviewImage.Source = source;
        }

        private void Image_MouseDown(object sender, MouseButtonEventArgs e)
        {
            if (_points.Count >= 4) return;

            var position = e.GetPosition(PreviewImage);
            _points.Add(position);  // 使用 System.Windows.Point

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
                System.Windows.MessageBox.Show("请选择4个点进行梯形校正", "提示", MessageBoxButton.OK, MessageBoxImage.Warning);
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
            MarkersCanvas.Children.Clear();
            _markers.Clear();
        }
    }
}
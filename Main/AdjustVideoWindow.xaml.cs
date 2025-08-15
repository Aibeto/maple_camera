using System.Windows;

namespace ShowWrite.Views
{
    public partial class AdjustVideoWindow : Window
    {
        public double Brightness { get; private set; }
        public double Contrast { get; private set; }

        public AdjustVideoWindow(double brightness, double contrast)
        {
            InitializeComponent();
            BrightnessSlider.Value = brightness;
            ContrastSlider.Value = contrast;
        }

        private void BrightnessSlider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            Brightness = BrightnessSlider.Value;
        }

        private void ContrastSlider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            Contrast = ContrastSlider.Value;
        }

        private void OK_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = true;
        }

        private void Cancel_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
        }
    }
}

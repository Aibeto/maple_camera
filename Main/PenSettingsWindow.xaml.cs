using System.Windows;
using System.Windows.Media;
using WinForms = System.Windows.Forms;

namespace ShowWrite
{
    public partial class PenSettingsWindow : Window
    {
        public System.Windows.Media.Color SelectedColor { get; private set; }
        public double SelectedWidth { get; private set; }

        public PenSettingsWindow(System.Windows.Media.Color currentColor, double currentWidth)
        {
            InitializeComponent();

            SelectedColor = currentColor;
            SelectedWidth = currentWidth;

            ColorPreview.Background = new SolidColorBrush(SelectedColor);
            WidthSlider.Value = SelectedWidth;
            WidthValue.Text = $"宽度: {SelectedWidth}";

            WidthSlider.ValueChanged += (s, e) =>
            {
                WidthValue.Text = $"宽度: {(int)e.NewValue}";
            };
        }

        private void ColorButton_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new WinForms.ColorDialog();
            dlg.Color = System.Drawing.Color.FromArgb(SelectedColor.A, SelectedColor.R, SelectedColor.G, SelectedColor.B);
            if (dlg.ShowDialog() == WinForms.DialogResult.OK)
            {
                SelectedColor = System.Windows.Media.Color.FromArgb(dlg.Color.A, dlg.Color.R, dlg.Color.G, dlg.Color.B);
                ColorPreview.Background = new SolidColorBrush(SelectedColor);
            }
        }

        private void Ok_Click(object sender, RoutedEventArgs e)
        {
            SelectedWidth = WidthSlider.Value;
            DialogResult = true;
        }

        private void Cancel_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
        }
    }
}

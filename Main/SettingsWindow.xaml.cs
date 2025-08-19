using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Windows;
using System.Windows.Controls;

namespace ShowWrite
{
    public partial class SettingsWindow : Window
    {
        private readonly AppConfig _config;
        private readonly List<string> _cameras;

        public SettingsWindow(AppConfig config, List<string> cameras)
        {
            InitializeComponent();
            _config = config;
            _cameras = cameras;
            Loaded += OnLoaded;
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            // 设置版本信息
#pragma warning disable CS8602 // 解引用可能出现空引用。
            VersionText.Text = Assembly.GetExecutingAssembly().GetName().Version.ToString();
#pragma warning restore CS8602 // 解引用可能出现空引用。

            // 初始化摄像头列表
            CameraComboBox.ItemsSource = _cameras;

            // 从配置文件加载当前设置
            LoadConfig();
        }

        private void LoadConfig()
        {
            // 启动设置
            StartMaximizedCheckBox.IsChecked = _config.StartMaximized;
            AutoStartCameraCheckBox.IsChecked = _config.AutoStartCamera;

            // 设置选中的摄像头
            if (_config.CameraIndex >= 0 && _config.CameraIndex < _cameras.Count)
            {
                CameraComboBox.SelectedIndex = _config.CameraIndex;
            }

            // 默认工具设置
            PenWidthSlider.Value = _config.DefaultPenWidth;

            // 设置画笔颜色
            foreach (ComboBoxItem item in PenColorComboBox.Items)
            {
                if (item.Tag?.ToString() == _config.DefaultPenColor)
                {
                    item.IsSelected = true;
                    break;
                }
            }


            // 高级设置
            EnableHardwareAccel.IsChecked = _config.EnableHardwareAcceleration;
            EnableFrameProcessing.IsChecked = _config.EnableFrameProcessing;

            // 帧率限制
            if (_config.FrameRateLimit >= 0 && _config.FrameRateLimit < FrameRateComboBox.Items.Count)
            {
                FrameRateComboBox.SelectedIndex = _config.FrameRateLimit;
            }
        }

        private void MenuList_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (MenuList.SelectedIndex == -1) return;

            // 根据选择显示对应的面板
            GeneralPanel.Visibility = MenuList.SelectedIndex == 0 ? Visibility.Visible : Visibility.Collapsed;
            AdvancedPanel.Visibility = MenuList.SelectedIndex == 1 ? Visibility.Visible : Visibility.Collapsed;
            AboutPanel.Visibility = MenuList.SelectedIndex == 2 ? Visibility.Visible : Visibility.Collapsed;
        }

        private void OkButton_Click(object sender, RoutedEventArgs e)
        {
            // 保存设置到配置对象
            _config.StartMaximized = StartMaximizedCheckBox.IsChecked ?? true;
            _config.AutoStartCamera = AutoStartCameraCheckBox.IsChecked ?? true;
            _config.CameraIndex = CameraComboBox.SelectedIndex;
            _config.DefaultPenWidth = PenWidthSlider.Value;

            // 获取选中的画笔颜色
            if (PenColorComboBox.SelectedItem is ComboBoxItem colorItem)
            {
                _config.DefaultPenColor = colorItem.Tag?.ToString() ?? "#FF0000FF";
            }

            // 高级设置
            _config.EnableHardwareAcceleration = EnableHardwareAccel.IsChecked ?? true;
            _config.EnableFrameProcessing = EnableFrameProcessing.IsChecked ?? false;
            _config.FrameRateLimit = FrameRateComboBox.SelectedIndex;

            DialogResult = true;
            Close();
        }

        private void VisitWebsiteButton_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                // 打开GitHub发布页
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
                {
                    FileName = "https://github.com/wwcrdrvf6u/ShowWrite/",
                    UseShellExecute = true // 必须设置为true才能打开URL
                });
            }
            catch (System.ComponentModel.Win32Exception ex)
            {
                // 处理可能的异常（如默认浏览器未设置）
                System.Windows.MessageBox.Show($"无法打开链接: {ex.Message}", "错误", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void CancelButton_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
            Close();
        }
    }
}
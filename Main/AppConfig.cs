using AForge;
using System.Collections.Generic;

namespace ShowWrite.Models
{
    public class AppConfig
    {
        public int CameraIndex { get; set; } = 0;
        public List<System.Drawing.PointF>? CorrectionPoints { get; set; }
        public int SourceWidth { get; set; }
        public int SourceHeight { get; set; }

        // 新增设置项
        public bool StartMaximized { get; set; } = true;
        public bool AutoStartCamera { get; set; } = true;
        public double DefaultPenWidth { get; set; } = 2.0;
        public string DefaultPenColor { get; set; } = "#FF0000FF"; // 蓝色
        public bool EnableHardwareAcceleration { get; set; } = true;
        public bool EnableFrameProcessing { get; set; } = false; // 新增
        public int FrameRateLimit { get; set; } = 2; // 对应ComboBox索引
    }


}

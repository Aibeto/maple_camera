using System.Collections.Generic;
using System.Drawing;

namespace ShowWrite.Models
{
    public class CameraConfig
    {
        public int CameraIndex { get; set; } = -1;
        public string CameraName { get; set; } = string.Empty;
        public ImageAdjustments Adjustments { get; set; } = new ImageAdjustments();
        public List<PointF> PerspectivePoints { get; set; } = new();
    }

    public class ImageAdjustments
    {
        public int Brightness { get; set; } = 100; // 100=原样
        public int Contrast { get; set; } = 100;   // 100=原样
        public int Orientation { get; set; } = 0;  // 角度
        public bool FlipHorizontal { get; set; } = false;
    }
}

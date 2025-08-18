using System.Collections.Generic;

namespace ShowWrite.Models
{
    public class AppConfig
    {
        public int CameraIndex { get; set; } = 0;
        public List<System.Drawing.PointF>? CorrectionPoints { get; set; }
        public int SourceWidth { get; set; }
        public int SourceHeight { get; set; }
    }
}

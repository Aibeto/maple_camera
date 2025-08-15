using System.Windows.Ink;
using System.Windows.Media.Imaging;

namespace ShowWrite.Models
{
    public class CapturedImage
    {
        /// <summary>
        /// 捕获的图片（支持读写，方便梯形校正等功能直接修改）
        /// </summary>
        public BitmapSource Image { get; set; }

        /// <summary>
        /// 图片对应的手写笔迹
        /// </summary>
        public StrokeCollection Strokes { get; set; }

        public CapturedImage(BitmapSource image)
        {
            Image = image;
            Strokes = new StrokeCollection();
        }
    }
}

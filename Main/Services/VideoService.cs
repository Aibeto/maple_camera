using System;
using System.Drawing;
using AForge.Video;
using AForge.Video.DirectShow;

namespace ShowWrite.Services
{
    public sealed class VideoService : IDisposable
    {
        private VideoCaptureDevice? _device;
        private readonly object _frameLock = new();
        private Bitmap? _current;
        private DateTime _last = DateTime.MinValue;
        public const double MinFrameIntervalMs = 33; // ~30fps

        public event Action<Bitmap>? OnNewFrameProcessed; // 已限制频率

        public bool Start(int cameraIndex)
        {
            var devices = new FilterInfoCollection(FilterCategory.VideoInputDevice);
            if (devices.Count == 0) return false;
            if (cameraIndex < 0 || cameraIndex >= devices.Count) cameraIndex = 0;

            _device = new VideoCaptureDevice(devices[cameraIndex].MonikerString);
            _device.NewFrame += Device_NewFrame;
            _device.Start();
            return true;
        }

        private void Device_NewFrame(object? sender, NewFrameEventArgs e)
        {
            double elapsed = (DateTime.Now - _last).TotalMilliseconds;
            if (elapsed < MinFrameIntervalMs) return;
            _last = DateTime.Now;

            lock (_frameLock)
            {
                _current?.Dispose();
                _current = (Bitmap)e.Frame.Clone();
            }
            OnNewFrameProcessed?.Invoke(GetFrameCopy()!);
        }

        public Bitmap? GetFrameCopy()
        {
            lock (_frameLock)
            {
                return _current == null ? null : new Bitmap(_current);
            }
        }

        public void Stop()
        {
            if (_device != null)
            {
                _device.SignalToStop();
                _device.NewFrame -= Device_NewFrame;
                _device = null;
            }
        }

        public List<string> GetAvailableCameras()//切换摄像头（获取摄像头列表）
                                                 //c#之父保佑我！！
        {
            var devices = new List<string>();
            for (int i = 0; ; i++)
            {
                try
                {
                    var cap = new VideoCaptureDevice(new FilterInfoCollection(FilterCategory.VideoInputDevice)[i].MonikerString);
                    devices.Add(new FilterInfoCollection(FilterCategory.VideoInputDevice)[i].Name);
                }
                catch
                {
                    break;
                }
            }
            return devices;
        }

        public void Dispose()
        {
            Stop();
            lock (_frameLock) { _current?.Dispose(); _current = null; }
        }
    }
}

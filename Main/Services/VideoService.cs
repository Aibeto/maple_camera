using System;
using System.Collections.Generic;
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

        public void AutoFocus() //自动对焦
        {
            if (_device == null) return; // 确保设备存在

            try
            {
                // 修复：直接使用 _device 字段
                _device.SetCameraProperty(
                    CameraControlProperty.Focus,
                    0,
                    CameraControlFlags.Auto  // 打开自动对焦
                );
            }
            catch (Exception ex)
            {
                Console.WriteLine($"自动对焦失败: {ex.Message}");
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

        public List<string> GetAvailableCameras()
        {
            var devices = new List<string>();
            var deviceCollection = new FilterInfoCollection(FilterCategory.VideoInputDevice);

            for (int i = 0; i < deviceCollection.Count; i++)
            {
                try
                {
                    devices.Add(deviceCollection[i].Name);
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
            lock (_frameLock)
            {
                _current?.Dispose();
                _current = null;
            }
        }
    }
}
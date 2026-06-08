import unittest
from unittest.mock import patch

from win_whisper_dictation.audio_devices import _PortAudioInputDevice, _WindowsCaptureDevice, list_input_devices, resolve_input_device


class AudioDeviceTests(unittest.TestCase):
    def test_list_input_devices_excludes_output_only_devices(self):
        devices = [
            {"name": "Studio Microphone", "max_input_channels": 2, "max_output_channels": 0, "hostapi": 0},
            {"name": "Headphones", "max_input_channels": 0, "max_output_channels": 2, "hostapi": 0},
        ]
        hostapis = [{"name": "Windows WASAPI"}]

        with patch("win_whisper_dictation.audio_devices._windows_capture_devices", return_value=[]), patch(
            "win_whisper_dictation.audio_devices.sd.query_devices", return_value=devices
        ), patch("win_whisper_dictation.audio_devices.sd.query_hostapis", return_value=hostapis):
            result = list_input_devices()

        self.assertEqual([device.name for device in result], ["Studio Microphone"])

    def test_list_input_devices_uses_windows_capture_endpoint_names(self):
        windows_devices = [
            _WindowsCaptureDevice(id="endpoint-a", name="Microphone Array (Realtek Audio)"),
            _WindowsCaptureDevice(id="endpoint-b", name="USB Studio Mic"),
        ]
        portaudio_devices = [
            _PortAudioInputDevice(index=1, name="Microphone Array (Realtek Audio)", hostapi="Windows WASAPI"),
            _PortAudioInputDevice(index=2, name="Speakers", hostapi="Windows WASAPI"),
            _PortAudioInputDevice(index=3, name="USB Studio Mic", hostapi="Windows WASAPI"),
        ]

        with patch("win_whisper_dictation.audio_devices._windows_capture_devices", return_value=windows_devices), patch(
            "win_whisper_dictation.audio_devices._portaudio_input_devices", return_value=portaudio_devices
        ):
            result = list_input_devices()

        self.assertEqual([device.display_name for device in result], ["Microphone Array (Realtek Audio)", "USB Studio Mic"])
        self.assertEqual([device.id for device in result], ["endpoint-a", "endpoint-b"])
        self.assertEqual([device.index for device in result], [1, 3])

    def test_resolve_missing_input_device_falls_back_to_default(self):
        with patch("win_whisper_dictation.audio_devices.list_input_devices", return_value=[]):
            device, fallback = resolve_input_device("Windows WASAPI::Missing")

        self.assertIsNone(device)
        self.assertTrue(fallback)


if __name__ == "__main__":
    unittest.main()

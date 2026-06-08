from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass, field

import sounddevice as sd


SYSTEM_MICROPHONE_ID = ""


@dataclass(frozen=True)
class AudioInputDevice:
    id: str
    name: str
    index: int | None
    aliases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def display_name(self) -> str:
        return self.name


@dataclass(frozen=True)
class _WindowsCaptureDevice:
    id: str
    name: str


@dataclass(frozen=True)
class _PortAudioInputDevice:
    index: int
    name: str
    hostapi: str


def list_input_devices() -> list[AudioInputDevice]:
    portaudio_devices = _portaudio_input_devices()
    windows_devices = _windows_capture_devices()

    if windows_devices:
        used_indices: set[int] = set()
        result: list[AudioInputDevice] = []
        for device in windows_devices:
            match = _match_portaudio_device(device.name, portaudio_devices, used_indices)
            if match:
                used_indices.add(match.index)
            result.append(
                AudioInputDevice(
                    id=device.id,
                    name=device.name,
                    index=match.index if match else None,
                    aliases=(_legacy_device_id(match.name, match.hostapi),) if match else (),
                )
            )
        return result

    return [
        AudioInputDevice(
            id=_legacy_device_id(device.name, device.hostapi),
            name=device.name,
            index=device.index,
        )
        for device in portaudio_devices
    ]


def resolve_input_device(device_id: str) -> tuple[int | None, bool]:
    normalized = (device_id or "").strip()
    if not normalized:
        return None, False
    for device in list_input_devices():
        if normalized == device.id or normalized in device.aliases:
            return (device.index, False) if device.index is not None else (None, True)
    return None, True


def _portaudio_input_devices() -> list[_PortAudioInputDevice]:
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception:
        return []

    result: list[_PortAudioInputDevice] = []
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels") or 0) <= 0:
            continue
        name = str(device.get("name") or "").strip()
        if not name:
            continue
        hostapi_index = int(device.get("hostapi") or 0)
        hostapi = ""
        if 0 <= hostapi_index < len(hostapis):
            hostapi = str(hostapis[hostapi_index].get("name") or "").strip()
        result.append(_PortAudioInputDevice(index=index, name=name, hostapi=hostapi))
    return result


def _match_portaudio_device(
    windows_name: str,
    devices: list[_PortAudioInputDevice],
    used_indices: set[int],
) -> _PortAudioInputDevice | None:
    candidates = [device for device in devices if device.index not in used_indices]
    normalized_windows_name = _normalize_device_name(windows_name)
    if not normalized_windows_name:
        return None

    for prefer_wasapi in (True, False):
        for device in candidates:
            if prefer_wasapi and "wasapi" not in device.hostapi.lower():
                continue
            normalized_name = _normalize_device_name(device.name)
            if normalized_name == normalized_windows_name:
                return device
        for device in candidates:
            if prefer_wasapi and "wasapi" not in device.hostapi.lower():
                continue
            normalized_name = _normalize_device_name(device.name)
            if normalized_name in normalized_windows_name or normalized_windows_name in normalized_name:
                return device
    return None


def _windows_capture_devices() -> list[_WindowsCaptureDevice]:
    if os.name != "nt":
        return []
    try:
        return _enumerate_windows_capture_devices()
    except Exception:
        return []


def _enumerate_windows_capture_devices() -> list[_WindowsCaptureDevice]:
    ole32 = ctypes.OleDLL("ole32")

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    def guid(value: str) -> GUID:
        result = GUID()
        ole32.CLSIDFromString(ctypes.c_wchar_p(value), ctypes.byref(result))
        return result

    class PropertyKey(ctypes.Structure):
        _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]

    class PropVariant(ctypes.Structure):
        _fields_ = [
            ("vt", wintypes.USHORT),
            ("wReserved1", wintypes.USHORT),
            ("wReserved2", wintypes.USHORT),
            ("wReserved3", wintypes.USHORT),
            ("value", ctypes.c_void_p),
        ]

    class IMMDeviceEnumerator(ctypes.Structure):
        pass

    class IMMDeviceCollection(ctypes.Structure):
        pass

    class IMMDevice(ctypes.Structure):
        pass

    class IPropertyStore(ctypes.Structure):
        pass

    LP_MMDEVICE_ENUMERATOR = ctypes.POINTER(IMMDeviceEnumerator)
    LP_MMDEVICE_COLLECTION = ctypes.POINTER(IMMDeviceCollection)
    LP_MMDEVICE = ctypes.POINTER(IMMDevice)
    LP_PROPERTY_STORE = ctypes.POINTER(IPropertyStore)

    class IMMDeviceEnumeratorVtbl(ctypes.Structure):
        _fields_ = [
            ("QueryInterface", ctypes.c_void_p),
            ("AddRef", ctypes.c_void_p),
            ("Release", ctypes.WINFUNCTYPE(wintypes.ULONG, LP_MMDEVICE_ENUMERATOR)),
            (
                "EnumAudioEndpoints",
                ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,
                    LP_MMDEVICE_ENUMERATOR,
                    ctypes.c_int,
                    wintypes.DWORD,
                    ctypes.POINTER(LP_MMDEVICE_COLLECTION),
                ),
            ),
            ("GetDefaultAudioEndpoint", ctypes.c_void_p),
            ("GetDevice", ctypes.c_void_p),
            ("RegisterEndpointNotificationCallback", ctypes.c_void_p),
            ("UnregisterEndpointNotificationCallback", ctypes.c_void_p),
        ]

    class IMMDeviceCollectionVtbl(ctypes.Structure):
        _fields_ = [
            ("QueryInterface", ctypes.c_void_p),
            ("AddRef", ctypes.c_void_p),
            ("Release", ctypes.WINFUNCTYPE(wintypes.ULONG, LP_MMDEVICE_COLLECTION)),
            ("GetCount", ctypes.WINFUNCTYPE(ctypes.HRESULT, LP_MMDEVICE_COLLECTION, ctypes.POINTER(wintypes.UINT))),
            ("Item", ctypes.WINFUNCTYPE(ctypes.HRESULT, LP_MMDEVICE_COLLECTION, wintypes.UINT, ctypes.POINTER(LP_MMDEVICE))),
        ]

    class IMMDeviceVtbl(ctypes.Structure):
        _fields_ = [
            ("QueryInterface", ctypes.c_void_p),
            ("AddRef", ctypes.c_void_p),
            ("Release", ctypes.WINFUNCTYPE(wintypes.ULONG, LP_MMDEVICE)),
            ("Activate", ctypes.c_void_p),
            (
                "OpenPropertyStore",
                ctypes.WINFUNCTYPE(ctypes.HRESULT, LP_MMDEVICE, wintypes.DWORD, ctypes.POINTER(LP_PROPERTY_STORE)),
            ),
            ("GetId", ctypes.WINFUNCTYPE(ctypes.HRESULT, LP_MMDEVICE, ctypes.POINTER(ctypes.c_wchar_p))),
        ]

    class IPropertyStoreVtbl(ctypes.Structure):
        _fields_ = [
            ("QueryInterface", ctypes.c_void_p),
            ("AddRef", ctypes.c_void_p),
            ("Release", ctypes.WINFUNCTYPE(wintypes.ULONG, LP_PROPERTY_STORE)),
            ("GetCount", ctypes.c_void_p),
            ("GetAt", ctypes.c_void_p),
            (
                "GetValue",
                ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,
                    LP_PROPERTY_STORE,
                    ctypes.POINTER(PropertyKey),
                    ctypes.POINTER(PropVariant),
                ),
            ),
        ]

    IMMDeviceEnumerator._fields_ = [("lpVtbl", ctypes.POINTER(IMMDeviceEnumeratorVtbl))]
    IMMDeviceCollection._fields_ = [("lpVtbl", ctypes.POINTER(IMMDeviceCollectionVtbl))]
    IMMDevice._fields_ = [("lpVtbl", ctypes.POINTER(IMMDeviceVtbl))]
    IPropertyStore._fields_ = [("lpVtbl", ctypes.POINTER(IPropertyStoreVtbl))]

    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.HRESULT
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(GUID),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = ctypes.HRESULT
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.PropVariantClear.argtypes = [ctypes.POINTER(PropVariant)]

    clsid_enumerator = guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
    iid_enumerator = guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
    pkey_friendly_name = PropertyKey(guid("{A45C254E-DF1C-4EFD-8020-67D146A850E0}"), 14)

    COINIT_APARTMENTTHREADED = 0x2
    RPC_E_CHANGED_MODE = -2147417850
    CLSCTX_INPROC_SERVER = 0x1
    DEVICE_STATE_ACTIVE = 0x1
    eCapture = 1
    STGM_READ = 0x0
    VT_LPWSTR = 31

    coinit_hr = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    should_uninitialize = coinit_hr >= 0
    if coinit_hr < 0 and coinit_hr != RPC_E_CHANGED_MODE:
        raise OSError(coinit_hr, "CoInitializeEx failed")

    enumerator = LP_MMDEVICE_ENUMERATOR()
    collection = LP_MMDEVICE_COLLECTION()
    try:
        enumerator_ptr = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(clsid_enumerator),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(iid_enumerator),
            ctypes.byref(enumerator_ptr),
        )
        if hr < 0:
            raise OSError(hr, "CoCreateInstance failed")
        enumerator = ctypes.cast(enumerator_ptr, LP_MMDEVICE_ENUMERATOR)

        hr = enumerator.contents.lpVtbl.contents.EnumAudioEndpoints(
            enumerator,
            eCapture,
            DEVICE_STATE_ACTIVE,
            ctypes.byref(collection),
        )
        if hr < 0:
            raise OSError(hr, "EnumAudioEndpoints failed")

        count = wintypes.UINT()
        hr = collection.contents.lpVtbl.contents.GetCount(collection, ctypes.byref(count))
        if hr < 0:
            raise OSError(hr, "GetCount failed")

        result: list[_WindowsCaptureDevice] = []
        seen_names: dict[str, int] = {}
        for index in range(count.value):
            device = LP_MMDEVICE()
            store = LP_PROPERTY_STORE()
            raw_id = ctypes.c_wchar_p()
            prop = PropVariant()
            try:
                hr = collection.contents.lpVtbl.contents.Item(collection, index, ctypes.byref(device))
                if hr < 0:
                    continue

                hr = device.contents.lpVtbl.contents.GetId(device, ctypes.byref(raw_id))
                if hr < 0 or not raw_id.value:
                    continue

                hr = device.contents.lpVtbl.contents.OpenPropertyStore(device, STGM_READ, ctypes.byref(store))
                if hr < 0:
                    continue

                hr = store.contents.lpVtbl.contents.GetValue(store, ctypes.byref(pkey_friendly_name), ctypes.byref(prop))
                if hr < 0 or prop.vt != VT_LPWSTR or not prop.value:
                    continue

                name = ctypes.wstring_at(prop.value).strip()
                if not name:
                    continue
                seen_names[name] = seen_names.get(name, 0) + 1
                display_name = f"{name} ({seen_names[name]})" if seen_names[name] > 1 else name
                result.append(_WindowsCaptureDevice(id=raw_id.value, name=display_name))
            finally:
                if prop.vt:
                    ole32.PropVariantClear(ctypes.byref(prop))
                if raw_id:
                    ole32.CoTaskMemFree(raw_id)
                if store:
                    store.contents.lpVtbl.contents.Release(store)
                if device:
                    device.contents.lpVtbl.contents.Release(device)
        return result
    finally:
        if collection:
            collection.contents.lpVtbl.contents.Release(collection)
        if enumerator:
            enumerator.contents.lpVtbl.contents.Release(enumerator)
        if should_uninitialize:
            ole32.CoUninitialize()


def _legacy_device_id(name: str, hostapi: str) -> str:
    return f"{hostapi.strip()}::{name.strip()}"


def _normalize_device_name(value: str) -> str:
    return " ".join((value or "").casefold().split())

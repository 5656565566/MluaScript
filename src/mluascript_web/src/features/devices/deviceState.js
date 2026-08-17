import { ref } from 'vue'

const DEVICE_PAGE_SIZE = 10

export function createDeviceState() {
  return {
    selectedSession: ref(''),
    sessions: ref([]),
    adbDevices: ref([]),
    emulatorDevices: ref([]),
    browserDevices: ref([]),
    win32Windows: ref([]),
    adbAddress: ref('127.0.0.1:5555'),
    screenshotBase64: ref(''),
    screenshotMimeType: ref('image/png'),
    screenshotImagePath: ref(''),
    screenshotPath: ref(''),
    deviceTab: ref('adb'),
    devicePageSize: ref(DEVICE_PAGE_SIZE),
    adbDevicePage: ref(1),
    emulatorDevicePage: ref(1),
    browserDevicePage: ref(1),
    win32DevicePage: ref(1),
    devicePreviewWindows: ref([]),
    devicePreviewIntervalMs: ref(1000),
    nextPreviewWindowOffset: ref(0),
  }
}

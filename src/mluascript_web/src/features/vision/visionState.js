import { ref } from 'vue'

export const DEFAULT_VISION_RECOGNITION = {
  kind: 'ocr',
  templatePath: '',
  modelPath: '',
  expected: '',
  targets: '',
  lower: '#000000',
  upper: '#ffffff',
  threshold: 0.8,
  result: null,
  error: '',
}

export function createVisionState() {
  return {
    visionSession: ref({
      source: {
        type: '',
        path: '',
        base64: '',
        mimeType: 'image/png',
        width: 0,
        height: 0,
      },
      point: null,
      roi: null,
      recognition: { ...DEFAULT_VISION_RECOGNITION },
    }),
  }
}

import {
  buildVisionLua,
  normalizeMaaPoint,
  normalizeMaaRoi,
  rawToMaaPoint,
  rawToMaaRoi,
} from './visionRecipe.js'
import { insertVisionRecipeIntoBlockly } from '../../blockly/visionInsertion.js'

function draftRoi(draft) {
  if (Number(draft?.roiWidth) <= 0 || Number(draft?.roiHeight) <= 0) return null
  return rawToMaaRoi({
    rawX: draft.roiX,
    rawY: draft.roiY,
    rawWidth: draft.roiWidth,
    rawHeight: draft.roiHeight,
    imageWidth: draft.imageWidth,
    imageHeight: draft.imageHeight,
  })
}

function sessionRoi(session) {
  return normalizeMaaRoi(session?.roi, session?.source || {})
}

export function createVisionActions({ state, getActions }) {
  function updateSession(patch) {
    state.visionSession.value = {
      ...state.visionSession.value,
      ...patch,
    }
    return state.visionSession.value
  }

  function syncDraftFromSession() {
    const session = state.visionSession.value
    const source = session.source || {}
    const roi = sessionRoi(session)
    const recognition = session.recognition || {}
    state.imageRecognitionDraft.value = {
      ...state.imageRecognitionDraft.value,
      kind: recognition.kind || 'ocr',
      imageBase64: source.base64 || '',
      imageMimeType: source.mimeType || 'image/png',
      imagePath: source.path || '',
      imageWidth: source.width || 0,
      imageHeight: source.height || 0,
      templatePath: recognition.templatePath || '',
      modelPath: recognition.modelPath || '',
      expected: recognition.expected || '',
      targets: recognition.targets || '',
      lower: recognition.lower || '#000000',
      upper: recognition.upper || '#ffffff',
      threshold: recognition.threshold ?? 0.8,
      roiX: roi ? (roi.rawX ?? roi.x) : null,
      roiY: roi ? (roi.rawY ?? roi.y) : null,
      roiWidth: roi ? (roi.rawWidth ?? roi.width) : null,
      roiHeight: roi ? (roi.rawHeight ?? roi.height) : null,
      result: recognition.result || null,
      error: recognition.error || '',
    }
    return state.imageRecognitionDraft.value
  }

  function syncSessionFromDraft() {
    const draft = state.imageRecognitionDraft.value || {}
    const roi = draftRoi(draft)
    return updateSession({
      source: {
        ...state.visionSession.value.source,
        type: draft.imagePath ? 'project-file' : state.visionSession.value.source?.type || 'image',
        path: draft.imagePath || '',
        base64: draft.imageBase64 || '',
        mimeType: draft.imageMimeType || 'image/png',
        width: Number(draft.imageWidth) || state.visionSession.value.source?.width || 0,
        height: Number(draft.imageHeight) || state.visionSession.value.source?.height || 0,
      },
      roi,
      recognition: {
        ...state.visionSession.value.recognition,
        kind: draft.kind || 'ocr',
        templatePath: draft.templatePath || '',
        modelPath: draft.modelPath || '',
        expected: draft.expected || '',
        targets: draft.targets || '',
        lower: draft.lower || '#000000',
        upper: draft.upper || '#ffffff',
        threshold: draft.threshold ?? 0.8,
        result: draft.result || null,
        error: draft.error || '',
      },
    })
  }

  return {
    setVisionSource(sourcePatch = {}) {
      const previous = state.visionSession.value.source || {}
      const source = {
        ...previous,
        ...sourcePatch,
      }
      const sourceChanged = source.path !== previous.path
        || source.base64 !== previous.base64
        || source.type !== previous.type
      updateSession({
        source,
        ...(sourceChanged ? { point: null, roi: null } : {}),
        ...(sourceChanged ? {
          recognition: {
            ...state.visionSession.value.recognition,
            result: null,
            error: '',
          },
        } : {}),
      })
      state.imageRecognitionDraft.value = {
        ...state.imageRecognitionDraft.value,
        imageBase64: source.base64 || '',
        imageMimeType: source.mimeType || 'image/png',
        imagePath: source.path || '',
        imageWidth: source.width || 0,
        imageHeight: source.height || 0,
        ...(sourceChanged ? {
          roiX: null,
          roiY: null,
          roiWidth: null,
          roiHeight: null,
          result: null,
          error: '',
        } : {}),
      }
      return source
    },

    setVisionPoint(point) {
      const source = state.visionSession.value.source || {}
      return updateSession({ point: rawToMaaPoint(point, source) })
    },

    setVisionRoi(roi) {
      const source = state.visionSession.value.source || {}
      return updateSession({ roi: rawToMaaRoi(roi, source) })
    },

    setVisionRecognition(patch = {}) {
      return updateSession({
        recognition: {
          ...state.visionSession.value.recognition,
          ...patch,
        },
      })
    },

    syncVisionDraftFromSession: syncDraftFromSession,
    syncVisionSessionFromDraft: syncSessionFromDraft,

    getVisionLua(options = {}) {
      const session = state.visionSession.value
      return buildVisionLua({
         mode: options.mode || 'recognition',
         point: session.point,
         roi: session.roi,
         recognition: session.recognition,
         color: options.color,
       }, options)
    },

    async copyVisionLua(options = {}) {
      if (!options.mode || options.mode === 'recognition') getActions().syncVisionSessionFromDraft?.()
      const code = getActions().getVisionLua(options)
      if (!code) throw new Error('当前没有可生成的视觉操作')
      await navigator.clipboard.writeText(code)
      getActions().setStatus('视觉 Lua 已复制', 'success')
      return code
    },

    insertVisionIntoBlockly(options = {}) {
      if (!options.mode || options.mode === 'recognition') getActions().syncVisionSessionFromDraft?.()
      const workspace = state.blocklyEditor.value
      if (!workspace) throw new Error('请先打开 Blockly 文件')
      const session = state.visionSession.value
      const root = insertVisionRecipeIntoBlockly(workspace, {
        mode: options.mode || 'recognition',
        point: session.point,
         roi: session.roi,
         recognition: session.recognition,
         color: options.color,
         clickResult: Boolean(options.clickResult),
        offsetX: options.offsetX,
        offsetY: options.offsetY,
      })
      getActions().setStatus('视觉积木已插入当前 Blockly 文件', 'success')
      return root
    },

    insertVisionIntoLua(options = {}) {
      if (!options.mode || options.mode === 'recognition') getActions().syncVisionSessionFromDraft?.()
      const code = getActions().getVisionLua(options)
      if (!code) throw new Error('当前没有可生成的视觉操作')
      const editor = state.textCodeEditor.value
      if (!editor?.insertText) throw new Error('请先打开 Lua 文件')
      editor.insertText(code)
      state.projectFileContent.value = state.projectFileContent.value
        ? `${state.projectFileContent.value}${code}`
        : code
      state.projectFileDirty.value = true
      getActions().setStatus('视觉 Lua 已插入当前编辑器', 'success')
      return code
    },
  }
}

export const TEMPLATE_AUTOSAVE_DELAY = 400

export function createTemplateAutosave({
  save,
  delay = TEMPLATE_AUTOSAVE_DELAY,
  scheduler = globalThis,
}) {
  let timer = null
  let pendingSnapshot = null
  let queue = Promise.resolve()
  let latestOperation = Promise.resolve()

  function clearScheduledSave() {
    if (timer === null) return
    scheduler.clearTimeout(timer)
    timer = null
  }

  function runPendingSave() {
    if (pendingSnapshot === null) return latestOperation
    const snapshot = pendingSnapshot
    pendingSnapshot = null
    const operation = queue.then(() => save(snapshot))
    latestOperation = operation
    // A failed save must not prevent the next edit from being persisted.
    queue = operation.catch(() => undefined)
    return operation
  }

  function schedule(snapshot) {
    pendingSnapshot = snapshot
    clearScheduledSave()
    timer = scheduler.setTimeout(() => {
      timer = null
      void runPendingSave().catch(() => undefined)
    }, delay)
  }

  async function flush(snapshot = undefined) {
    if (snapshot !== undefined) pendingSnapshot = snapshot
    clearScheduledSave()

    while (true) {
      if (pendingSnapshot !== null) await runPendingSave()
      else await latestOperation
      if (pendingSnapshot === null) return
      clearScheduledSave()
    }
  }

  function cancelPending() {
    clearScheduledSave()
    pendingSnapshot = null
  }

  return {
    schedule,
    flush,
    cancelPending,
  }
}

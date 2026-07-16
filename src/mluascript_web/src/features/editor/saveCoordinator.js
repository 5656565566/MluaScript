export function createSaveCoordinator() {
  let generation = 0
  let queue = Promise.resolve()

  function beginDocumentTransition() {
    generation += 1
    return generation
  }

  function enqueue({ documentGeneration = generation, execute, commit }) {
    const operation = queue.then(async () => {
      const result = await execute()
      if (documentGeneration === generation) {
        await commit(result)
      }
      return result
    })

    // A failed save must not poison subsequent saves in the queue.
    queue = operation.catch(() => undefined)
    return operation
  }

  return {
    beginDocumentTransition,
    currentGeneration: () => generation,
    isCurrent: (value) => value === generation,
    enqueue,
  }
}


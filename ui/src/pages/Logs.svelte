<script>
  let logs = $state([])
  let paused = $state(false)
  let levelFilter = $state('all')
  let container

  $effect(() => {
    const es = new EventSource('/api/logs/stream')
    es.onmessage = (e) => {
      if (paused) return
      try {
        const entry = JSON.parse(e.data)
        logs = [...logs.slice(-500), entry]
        // auto-scroll
        if (container) {
          requestAnimationFrame(() => container.scrollTop = container.scrollHeight)
        }
      } catch {}
    }
    es.onerror = () => {}
    return () => es.close()
  })

  function filteredLogs() {
    if (levelFilter === 'all') return logs
    return logs.filter(l => l.level === levelFilter)
  }

  function levelColor(level) {
    switch (level) {
      case 'error': return 'var(--red)'
      case 'warning': return 'var(--yellow)'
      case 'info': return 'var(--green)'
      case 'debug': return 'var(--sidebar-text)'
      default: return 'var(--text)'
    }
  }
</script>

<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
  <h2>Logs</h2>
  <div style="display: flex; gap: 8px; align-items: center;">
    <select bind:value={levelFilter} style="width: auto;">
      <option value="all">All Levels</option>
      <option value="debug">Debug</option>
      <option value="info">Info</option>
      <option value="warning">Warning</option>
      <option value="error">Error</option>
    </select>
    <button onclick={() => paused = !paused}>
      {paused ? 'Resume' : 'Pause'}
    </button>
    <button onclick={() => logs = []}>Clear</button>
  </div>
</div>

<div class="log-container" bind:this={container}>
  {#each filteredLogs() as log}
    <div class="log-line" style="color: {levelColor(log.level)}">
      <span style="color: var(--sidebar-text)">{log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}</span>
      <span style="color: {levelColor(log.level)}">[{log.level || '?'}]</span>
      {log.event || ''}
      {#if log.provider} <span style="color: var(--accent)">provider={log.provider}</span>{/if}
      {#if log.model} <span style="color: var(--accent)">model={log.model}</span>{/if}
      {#if log.error} <span style="color: var(--red)">error={log.error}</span>{/if}
    </div>
  {/each}
  {#if logs.length === 0}
    <div style="color: var(--sidebar-text); padding: 20px;">Waiting for logs...</div>
  {/if}
</div>

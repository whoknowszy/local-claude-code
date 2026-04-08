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

  // Format a value for display
  function fmt(val) {
    if (val === null || val === undefined) return ''
    if (typeof val === 'object') return JSON.stringify(val)
    return String(val)
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
    <div class="log-entry">
      <span class="log-ts">{log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}</span>
      <span class="log-level" style="color: {levelColor(log.level)}">[{log.level || '?'}]</span>
      <span class="log-event">{log.event || ''}</span>
      {#if log.provider}<span class="log-field" style="color: var(--accent)">provider={fmt(log.provider)}</span>{/if}
      {#if log.model}<span class="log-field" style="color: var(--accent)">model={fmt(log.model)}</span>{/if}
      {#if log.client_ip}<span class="log-field">client_ip={fmt(log.client_ip)}</span>{/if}
      {#if log.input_tokens !== undefined}<span class="log-field">in={fmt(log.input_tokens)}</span>{/if}
      {#if log.output_tokens !== undefined}<span class="log-field">out={fmt(log.output_tokens)}</span>{/if}
      {#if log.latency_ms !== undefined}<span class="log-field">{fmt(log.latency_ms)}ms</span>{/if}
      {#if log.finish_reason}<span class="log-field">reason={fmt(log.finish_reason)}</span>{/if}
      {#if log.scenario}<span class="log-field" style="color: var(--yellow)">scenario={fmt(log.scenario)}</span>{/if}
      {#if log.error}<span class="log-field" style="color: var(--red)">error={fmt(log.error)}</span>{/if}
      {#if log.request_id}<span class="log-field" style="color: var(--sidebar-text)">req={fmt(log.request_id)}</span>{/if}
      {#if log.route_reason}<span class="log-field" style="color: var(--sidebar-text)">{fmt(log.route_reason)}</span>{/if}
      {#if log.final_provider}<span class="log-field">→{fmt(log.final_provider)}</span>{/if}
      {#if log.via_fallback}<span class="log-field" style="color: var(--yellow)">fallback</span>{/if}
      {#if log.fallback_failed}<span class="log-field" style="color: var(--red)">fallback_failed</span>{/if}
      {#if log.stream !== undefined}<span class="log-field">stream={fmt(log.stream)}</span>{/if}
    </div>
  {/each}
  {#if logs.length === 0}
    <div style="color: var(--sidebar-text); padding: 20px;">Waiting for logs...</div>
  {/if}
</div>

<style>
  .log-entry {
    display: flex;
    flex-wrap: wrap;
    gap: 0 8px;
    align-items: baseline;
    padding: 2px 0;
    border-bottom: 1px solid rgba(128, 128, 128, 0.1);
    font-family: monospace;
    font-size: 12px;
  }
  .log-ts {
    color: var(--sidebar-text);
    flex-shrink: 0;
  }
  .log-level {
    flex-shrink: 0;
    min-width: 56px;
  }
  .log-event {
    color: var(--text);
    flex-shrink: 0;
    font-weight: 500;
  }
  .log-field {
    flex-shrink: 0;
  }
</style>

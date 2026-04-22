<script>
  let {
    provider,
    healthStatus = null,
    editing = false,
    onedit = () => {},
    ondelete = () => {},
    ontoggle = () => {},
    ondragstart = () => {},
    ondragover = () => {},
    ondragend = () => {},
    ondrop = () => {},
    dragPosition = null,
    isDropTarget = false,
    index = 0,
  } = $props()

  let isDragging = $state(false)

  function chipClass(type) {
    return type === 'openai' ? 'chip-openai' : 'chip-anthropic'
  }

  function healthDotClass(status) {
    return status || 'healthy'
  }

  function healthLabel(status) {
    if (status === 'degraded') return '已降级'
    if (status === 'recovering') return '恢复中'
    return '正常'
  }

  function getDropPosition(event) {
    const rect = event.currentTarget.getBoundingClientRect()
    return event.clientY < rect.top + rect.height / 2 ? 'before' : 'after'
  }

  function handleDragStart(event) {
    isDragging = true
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', provider.name)
    ondragstart(event, provider.name)
  }

  function handleDragOver(event) {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
    ondragover(event, provider.name, getDropPosition(event))
  }

  function handleDrop(event) {
    event.preventDefault()
    ondrop(event, provider.name, getDropPosition(event))
  }
</script>

<div
  class="provider-card {provider.enabled === false ? 'disabled-provider' : ''} {isDragging ? 'dragging' : ''} {isDropTarget && dragPosition === 'before' ? 'drop-before' : ''} {isDropTarget && dragPosition === 'after' ? 'drop-after' : ''}"
  role="listitem"
  aria-label={`${provider.name} provider`}
  draggable={editing}
  ondragstart={handleDragStart}
  ondragover={handleDragOver}
  ondragend={() => { isDragging = false; ondragend() }}
  ondrop={handleDrop}
>
  {#if editing}
    <div class="drag-handle" title="拖拽排序">
      <svg viewBox="0 0 16 16" fill="currentColor">
        <circle cx="5" cy="3" r="1.5"/>
        <circle cx="11" cy="3" r="1.5"/>
        <circle cx="5" cy="8" r="1.5"/>
        <circle cx="11" cy="8" r="1.5"/>
        <circle cx="5" cy="13" r="1.5"/>
        <circle cx="11" cy="13" r="1.5"/>
      </svg>
    </div>
  {/if}

  <div class="card-body">
    <div class="card-header">
      <span class="provider-name">{provider.name}</span>
      <span class="badge badge-blue">{provider.type}</span>
      {#if healthStatus}
        <span class="health-dot {healthDotClass(healthStatus.status)}"></span>
        <span class="health-label {healthDotClass(healthStatus.status)}">{healthLabel(healthStatus.status)}</span>
      {/if}
    </div>
    <div class="card-meta">
      <span>优先级: {provider.priority ?? 100}</span>
      <span>认证: {provider.auth_scheme}</span>
      <span title={provider.base_url} style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
        {provider.base_url}
      </span>
    </div>
    <div class="model-chips">
      {#each (provider.models || []) as m}
        <span class="model-chip {chipClass(provider.type)}">{m}</span>
      {/each}
      {#if (provider.models || []).length === 0}
        <span style="font-size: 11px; color: var(--sidebar-text);">暂无模型</span>
      {/if}
    </div>
  </div>

  <div class="card-actions">
    <label class="toggle-switch" title={!editing ? '编辑模式才能操作' : (provider.enabled !== false ? '停用（排除出路由）' : '启用')}>
      <input type="checkbox" checked={provider.enabled !== false} disabled={!editing} onchange={ontoggle} />
      <span class="toggle-slider"></span>
    </label>
    {#if editing}
      <button onclick={onedit}>编辑</button>
      <button class="btn-danger" onclick={ondelete}>删除</button>
    {/if}
  </div>
</div>

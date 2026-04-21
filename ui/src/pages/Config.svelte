<script>
  import { api } from '../api.js'
  import ProviderCard from '../components/ProviderCard.svelte'

  let config = $state(null)
  let error = $state('')
  let saved = $state(false)
  let editing = $state(false)

  // Claude settings state
  let claudeEnvJson = $state('')
  let claudeEnvSaved = $state(false)
  let claudeEnvError = $state('')
  let claudeEnvEditing = $state(false)

  // model_map structured entries
  let modelMapEntries = $state([])

  function addModelMapEntry() {
    modelMapEntries = [...modelMapEntries, {
      alias: '',
      mode: 'single',
      routes: [{ provider: providerList[0]?.name || '', model: providerList[0]?.models?.[0] || '' }],
    }]
  }

  function removeModelMapEntry(idx) {
    modelMapEntries = modelMapEntries.filter((_, i) => i !== idx)
  }

  function addModelMapRoute(idx) {
    const entries = [...modelMapEntries]
    entries[idx].routes = [...entries[idx].routes, { provider: '', model: '' }]
    modelMapEntries = entries
  }

  function removeModelMapRoute(entryIdx, routeIdx) {
    const entries = [...modelMapEntries]
    entries[entryIdx].routes = entries[entryIdx].routes.filter((_, i) => i !== routeIdx)
    modelMapEntries = entries
  }

// Provider modal state
  let showModal = $state(false)
  let editingIdx = $state(-1)
  let form = $state({
    name: '', type: 'anthropic', base_url: '', api_key: '',
    auth_scheme: 'x-api-key', models: [], timeout: 600, priority: 100,
    enabled: true,
  })

  // 模型标签输入（modal 内）
  let formModelInput = $state('')

  // Health status
  let healthData = $state(null)

  // Drag-and-drop state
  let dragIndex = $state(-1)
  let dropIndex = $state(-1)

  function addModel() {
    const m = formModelInput.trim()
    if (!m || form.models.includes(m)) { formModelInput = ''; return }
    form.models = [...form.models, m]
    formModelInput = ''
  }

  // Provider list for selects (enabled providers only)
  let providerList = $derived.by(() => {
    return (config?.providers || []).filter(p => p.enabled !== false).map(p => ({ name: p.name, models: p.models || [] }))
  })

  // Sorted providers for table display (by priority, then name)
  let sortedProviders = $derived.by(() => {
    return [...(config?.providers || [])].sort((a, b) => (a.priority ?? 100) - (b.priority ?? 100) || a.name.localeCompare(b.name))
  })

  // Route split state: default
  let defaultProvider = $state('')
  let defaultModel = $state('')
  let defaultModelOptions = $derived.by(() => {
    if (!defaultProvider) return []
    const p = providerList.find(p => p.name === defaultProvider)
    return p ? p.models : []
  })

  // Route split state: fallback
  let fallbackProvider = $state('')
  let fallbackModel = $state('')
  let fallbackModelOptions = $derived.by(() => {
    if (!fallbackProvider) return []
    const p = providerList.find(p => p.name === fallbackProvider)
    return p ? p.models : []
  })

  // Guard: prevents sync $effects from overwriting config during initial load()
  let routeInitialized = $state(false)

  // Sync default route to config on change (only after load() has parsed initial values)
  $effect(() => {
    if (!config || !routeInitialized) return
    config.router.default = (defaultProvider && defaultModel) ? `${defaultProvider},${defaultModel}` : ''
  })

  // Sync fallback route to config on change
  $effect(() => {
    if (!config || !routeInitialized) return
    config.router.fallback = (fallbackProvider && fallbackModel) ? `${fallbackProvider},${fallbackModel}` : ''
  })

  // Sync model_map entries to config on change
  $effect(() => {
    if (!config || !routeInitialized) return
    const mm = {}
    for (const entry of modelMapEntries) {
      if (!entry.alias.trim()) continue
      if (entry.mode === 'single') {
        const r = entry.routes[0]
        if (r?.provider && r?.model) {
          mm[entry.alias] = `${r.provider},${r.model}`
        }
      } else {
        const routes = entry.routes
          .filter(r => r.provider && r.model)
          .map(r => `${r.provider},${r.model}`)
        if (routes.length > 0) {
          mm[entry.alias] = routes
        }
      }
    }
    config.router.model_map = mm
  })

  async function load() {
    try {
      routeInitialized = false
      config = await api.getConfig(true)
      const def = config?.router?.default || ''
      if (def) {
        const [prov, ...modelParts] = def.split(',')
        defaultProvider = prov || ''
        defaultModel = modelParts.join(',')
      }
      const fb = config?.router?.fallback || ''
      if (fb) {
        const [prov, ...modelParts] = fb.split(',')
        fallbackProvider = prov || ''
        fallbackModel = modelParts.join(',')
      }
      const mm = config?.router?.model_map || {}
      modelMapEntries = Object.entries(mm).map(([alias, routeValue]) => {
        if (Array.isArray(routeValue)) {
          return {
            alias,
            mode: 'fallback',
            routes: routeValue.map(r => {
              const [p, ...mParts] = String(r).split(',')
              return { provider: p || '', model: mParts.join(',') || '' }
            }),
          }
        } else {
          const [p, ...mParts] = String(routeValue).split(',')
          return {
            alias,
            mode: 'single',
            routes: [{ provider: p || '', model: mParts.join(',') || '' }],
          }
        }
      })
      routeInitialized = true
    } catch (e) {
      error = e.message
    }
  }

  $effect(() => { load() })

  function openCreate() {
    editingIdx = -1
    form = { name: '', type: 'anthropic', base_url: '', api_key: '', auth_scheme: 'x-api-key', models: [], timeout: 600, priority: 100, enabled: true }
    formModelInput = ''
    showModal = true
  }

  function openEdit(idx) {
    const p = config.providers[idx]
    editingIdx = idx
    form = {
      name: p.name, type: p.type, base_url: p.base_url,
      api_key: '',
      auth_scheme: p.auth_scheme || 'x-api-key',
      models: [...(p.models || [])],
      timeout: p.timeout || 600,
      priority: p.priority ?? 100,
      enabled: p.enabled !== false,
    }
    formModelInput = ''
    showModal = true
  }

  function saveProvider() {
    const provider = {
      name: form.name,
      type: form.type,
      base_url: form.base_url,
      auth_scheme: form.auth_scheme,
      models: form.models,
      timeout: form.timeout,
      priority: form.priority,
      enabled: form.enabled !== false,
    }
    if (form.api_key) provider.api_key = form.api_key

    if (editingIdx >= 0) {
      if (!provider.api_key) provider.api_key = config.providers[editingIdx].api_key
      config.providers[editingIdx] = provider
    } else {
      config.providers = [...config.providers, provider]
    }
    showModal = false
  }

  function removeProvider(idx) {
    if (!confirm(`删除 Provider "${config.providers[idx].name}"？`)) return
    config.providers = config.providers.filter((_, i) => i !== idx)
  }

  function toggleProvider(idx) {
    const providers = [...config.providers]
    providers[idx] = { ...providers[idx], enabled: !(providers[idx].enabled !== false) }
    config.providers = providers
  }

  async function save() {
    error = ''
    saved = false
    try {
      await api.updateConfig(config)
      saved = true
      editing = false
      setTimeout(() => saved = false, 2000)
    } catch (e) {
      error = e.message
    }
  }

  function cancelEdit() {
    load()
    editing = false
  }

  async function loadClaudeEnv() {
    try {
      const data = await api.getClaudeEnv()
      claudeEnvJson = JSON.stringify(data, null, 2)
    } catch (e) {
      claudeEnvError = e.message
    }
  }

  $effect(() => { loadClaudeEnv() })

  async function saveClaudeEnv() {
    claudeEnvError = ''
    claudeEnvSaved = false
    try {
      const parsed = JSON.parse(claudeEnvJson)
      await api.updateClaudeEnv(parsed)
      claudeEnvSaved = true
      claudeEnvEditing = false
      loadClaudeEnv()
      setTimeout(() => claudeEnvSaved = false, 2000)
    } catch (e) {
      claudeEnvError = e.message
    }
  }

  async function loadHealth() {
    try {
      healthData = await api.getHealth()
    } catch (e) {
      // Silently ignore - health is supplementary info
    }
  }

  $effect(() => {
    loadHealth()
    const timer = setInterval(loadHealth, 5000)
    return () => clearInterval(timer)
  })

  function handleDragStart(e, idx) {
    dragIndex = idx
  }

  function handleDragOver(e, idx) {
    dropIndex = idx
  }

  function handleDrop(e, idx) {
    if (dragIndex >= 0 && dragIndex !== idx) {
      reorderProviders(dragIndex, idx)
    }
    dragIndex = -1
    dropIndex = -1
  }

  function handleDragEnd() {
    dragIndex = -1
    dropIndex = -1
  }

  function reorderProviders(fromIdx, toIdx) {
    // Work on the original (unsorted) providers array
    const providers = [...config.providers]
    const [moved] = providers.splice(fromIdx, 1)
    providers.splice(toIdx, 0, moved)
    // Reassign priorities based on new order
    providers.forEach((p, i) => {
      p.priority = (i + 1) * 10  // 10, 20, 30, ...
    })
    config.providers = providers
  }
</script>

<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
  <h2>配置</h2>
  {#if config}
    {#if !editing}
      <button class="btn-primary" onclick={() => editing = true}>编辑</button>
    {:else}
      <div style="display: flex; gap: 8px;">
        <button class="btn-primary" onclick={save}>保存</button>
        <button onclick={cancelEdit}>取消</button>
      </div>
    {/if}
  {/if}
</div>

{#if error}
  <div class="card" style="color: var(--red)">{error}</div>
{/if}
{#if saved}
  <div class="card" style="color: var(--green)">配置已保存！</div>
{/if}

{#if config}
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
    <!-- Left column: Server + Logging -->
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <!-- Server -->
      <div class="card">
        <h2>服务器</h2>
        <div class="form-row">
          <div class="form-group">
            <label>Host</label>
            <input bind:value={config.server.host} disabled={!editing} />
          </div>
          <div class="form-group">
            <label>Port</label>
            <input type="number" bind:value={config.server.port} disabled={!editing} />
          </div>
          <div class="form-group">
            <label>代理 API Key（可选）</label>
            <input bind:value={config.server.api_key} placeholder="留空则不启用代理认证" disabled={!editing} />
          </div>
        </div>
      </div>

      <!-- Logging -->
      <div class="card">
        <h2>日志</h2>
        <div class="form-row">
          <div class="form-group">
            <label>日志级别</label>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              {#each ['debug', 'info', 'warning', 'error'] as lv}
                <label style="display: flex; align-items: center; gap: 4px; font-weight: normal; cursor: pointer;">
                  <input type="checkbox"
                    checked={config.logging.level?.includes?.(lv)}
                    disabled={!editing}
                    onchange={(e) => {
                      const levels = ['debug', 'info', 'warning', 'error']
                      let cur = config.logging.level || ''
                      if (typeof cur === 'string' && !cur.includes(',')) cur = cur
                      let selected = cur ? cur.split(',').filter(Boolean) : []
                      if (e.target.checked) {
                        if (!selected.includes(lv)) selected.push(lv)
                      } else {
                        selected = selected.filter(l => l !== lv)
                      }
                      const order = ['debug', 'info', 'warning', 'error']
                      selected.sort((a, b) => order.indexOf(a) - order.indexOf(b))
                      config.logging.level = selected.join(',')
                    }}
                  />
                  {lv}
                </label>
              {/each}
            </div>
          </div>
          <div class="form-group">
            <label>日志目录</label>
            <input bind:value={config.logging.log_dir} placeholder="~/.lccg/logs" disabled={!editing} />
          </div>
        </div>
      </div>

      <!-- Providers -->
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <h2 style="margin-bottom: 0;">Providers</h2>
          {#if editing}
            <button class="btn-primary" onclick={openCreate}>+ 添加 Provider</button>
          {/if}
        </div>
        {#if config.providers.length === 0}
          <div class="empty">暂无 Provider</div>
        {:else}
          <div class="provider-cards">
            {#each sortedProviders as p}
              {@const origIdx = config.providers.findIndex(x => x.name === p.name)}
              {@const pHealth = healthData?.providers?.[p.name] || null}
              <ProviderCard
                provider={p}
                healthStatus={pHealth}
                editing={editing}
                index={origIdx}
                onedit={() => openEdit(origIdx)}
                ondelete={() => removeProvider(origIdx)}
                ontoggle={() => toggleProvider(origIdx)}
                ondragstart={handleDragStart}
                ondragover={handleDragOver}
                ondrop={handleDrop}
                ondragend={handleDragEnd}
              />
            {/each}
          </div>
        {/if}
      </div>

    </div>

    <!-- Right column: Router -->
    <div class="card">
      <h2>路由</h2>
      <div class="form-row">
        <div class="form-group">
          <label>默认路由 Provider</label>
          <select bind:value={defaultProvider} disabled={!editing}>
            <option value="">-- 不设置 --</option>
            {#each providerList as p}
              <option value={p.name}>{p.name}</option>
            {/each}
          </select>
        </div>
        <div class="form-group">
          <label>默认路由模型</label>
          <select bind:value={defaultModel} disabled={!editing || !defaultProvider}>
            <option value="">-- 选择模型 --</option>
            {#each defaultModelOptions as m}
              <option value={m}>{m}</option>
            {/each}
          </select>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>故障回退路由 Provider</label>
          <select bind:value={fallbackProvider} disabled={!editing}>
            <option value="">-- 不设置 --</option>
            {#each providerList as p}
              <option value={p.name}>{p.name}</option>
            {/each}
          </select>
        </div>
        <div class="form-group">
          <label>故障回退路由模型</label>
          <select bind:value={fallbackModel} disabled={!editing || !fallbackProvider}>
            <option value="">-- 选择模型 --</option>
            {#each fallbackModelOptions as m}
              <option value={m}>{m}</option>
            {/each}
          </select>
        </div>
      </div>
      <!-- model_map: structured alias mapping table -->
      <div class="form-group" style="margin-top: 12px;">
        <label>模型别名映射（model_map）</label>
        {#if modelMapEntries.length === 0}
          <div style="font-size: 12px; color: var(--sidebar-text); padding: 4px 0;">暂无别名映射，点击下方按钮添加</div>
        {:else}
          <table style="width: 100%; font-size: 12px; border-collapse: collapse; margin-bottom: 4px;">
            <thead>
              <tr style="background: var(--border);">
                <th style="padding: 4px 8px; text-align: left;">别名</th>
                <th style="padding: 4px 8px; text-align: left;">模式</th>
                <th style="padding: 4px 8px; text-align: left;">Provider</th>
                <th style="padding: 4px 8px; text-align: left;">模型</th>
                <th style="padding: 4px 8px; width: 80px;"></th>
              </tr>
            </thead>
            <tbody>
              {#each modelMapEntries as entry, entryIdx}
                <tr>
                  <td rowspan={entry.mode === 'fallback' ? Math.max(entry.routes.length, 1) : 1} style="padding: 4px 8px; vertical-align: top;">
                    <input
                      bind:value={entry.alias}
                      disabled={!editing}
                      placeholder="claude-sonnet-4-6"
                      style="width: 130px; font-family: monospace; font-size: 12px;"
                    />
                  </td>
                  <td rowspan={entry.mode === 'fallback' ? Math.max(entry.routes.length, 1) : 1} style="padding: 4px 8px; vertical-align: top;">
                    <select bind:value={entry.mode} disabled={!editing} onchange={() => {
                      if (entry.mode === 'fallback' && entry.routes.length === 1) {
                        const entries = [...modelMapEntries]
                        entries[entryIdx].routes = [...entries[entryIdx].routes, { provider: '', model: '' }]
                        modelMapEntries = entries
                      }
                    }}>
                      <option value="single">单路由</option>
                      <option value="fallback">回退链</option>
                    </select>
                  </td>
                  <td style="padding: 2px 4px;">
                    <select bind:value={entry.routes[0].provider} disabled={!editing}>
                      <option value="">--</option>
                      {#each providerList as p}
                        <option value={p.name}>{p.name}</option>
                      {/each}
                    </select>
                  </td>
                  <td style="padding: 2px 4px;">
                    <select bind:value={entry.routes[0].model} disabled={!editing || !entry.routes[0].provider}>
                      <option value="">--</option>
                      {#each (providerList.find(p => p.name === entry.routes[0].provider)?.models || []) as m}
                        <option value={m}>{m}</option>
                      {/each}
                    </select>
                  </td>
                  <td rowspan={entry.mode === 'fallback' ? Math.max(entry.routes.length, 1) : 1} style="padding: 4px 8px; vertical-align: top;">
                    <button onclick={() => addModelMapRoute(entryIdx)} disabled={!editing} title="添加回退路由" style="padding: 1px 6px;">+</button>
                    <button onclick={() => removeModelMapEntry(entryIdx)} disabled={!editing} class="btn-danger" title="删除此别名" style="padding: 1px 6px;">x</button>
                  </td>
                </tr>
                {#if entry.mode === 'fallback'}
                  {#each entry.routes.slice(1) as route, routeIdx}
                    <tr>
                      <td style="padding: 2px 4px; padding-left: 24px;">
                        <select bind:value={route.provider} disabled={!editing}>
                          <option value="">--</option>
                          {#each providerList as p}
                            <option value={p.name}>{p.name}</option>
                          {/each}
                        </select>
                      </td>
                      <td style="padding: 2px 4px;">
                        <select bind:value={route.model} disabled={!editing || !route.provider}>
                          <option value="">--</option>
                          {#each (providerList.find(p => p.name === route.provider)?.models || []) as m}
                            <option value={m}>{m}</option>
                          {/each}
                        </select>
                      </td>
                      <td>
                        <button onclick={() => removeModelMapRoute(entryIdx, routeIdx + 1)} disabled={!editing} class="btn-danger" title="删除" style="padding: 1px 6px;">x</button>
                      </td>
                    </tr>
                  {/each}
                {/if}
              {/each}
            </tbody>
          </table>
        {/if}
        {#if editing}
          <button onclick={addModelMapEntry} style="margin-top: 4px;">+ 添加别名映射</button>
        {/if}
      </div>

      <!-- Degradation config -->
      <div class="form-group" style="margin-top: 16px;">
        <label>故障降级配置</label>
        <div class="form-row">
          <div class="form-group">
            <label>失败阈值</label>
            <input type="number" bind:value={config.router.degradation.failure_threshold} disabled={!editing} min="1" max="100" />
            <div style="font-size: 11px; color: var(--sidebar-text);">连续失败次数达到此值后降级</div>
          </div>
          <div class="form-group">
            <label>恢复等待（秒）</label>
            <input type="number" bind:value={config.router.degradation.recovery_seconds} disabled={!editing} min="1" />
            <div style="font-size: 11px; color: var(--sidebar-text);">降级后等待此时间进入恢复探测</div>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>探测间隔（秒）</label>
            <input type="number" bind:value={config.router.degradation.half_open_interval} disabled={!editing} min="1" />
            <div style="font-size: 11px; color: var(--sidebar-text);">恢复状态下每次探测的间隔</div>
          </div>
          <div class="form-group">
            <label>探测请求数</label>
            <input type="number" bind:value={config.router.degradation.half_open_max_requests} disabled={!editing} min="1" max="10" />
            <div style="font-size: 11px; color: var(--sidebar-text);">每个探测间隔允许的最大请求数</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Claude Code Settings -->
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
      <h2 style="margin-bottom: 0;">Claude Code 设置</h2>
      {#if !claudeEnvEditing}
        <button class="btn-primary" onclick={() => claudeEnvEditing = true}>编辑</button>
      {:else}
        <div style="display: flex; gap: 8px;">
          <button class="btn-primary" onclick={saveClaudeEnv}>保存</button>
          <button onclick={() => { claudeEnvEditing = false; loadClaudeEnv() }}>取消</button>
        </div>
      {/if}
    </div>
    {#if claudeEnvError}
      <div style="color: var(--red); margin-bottom: 8px;">{claudeEnvError}</div>
    {/if}
    {#if claudeEnvSaved}
      <div style="color: var(--green); margin-bottom: 8px;">已保存！</div>
    {/if}
    <div style="display: flex; gap: 8px; align-items: flex-start;">
      <textarea
        bind:value={claudeEnvJson}
        disabled={!claudeEnvEditing}
        rows="5"
        style="font-family: monospace; font-size: 12px; resize: vertical; min-width: 300px; flex: 1;"
      ></textarea>
    </div>
    <div style="font-size: 12px; color: var(--sidebar-text); margin-top: 4px;">
      直接编辑 Claude Code 的 <code>~/.claude/settings.json</code>，保存后立即生效。
    </div>
  </div>
{:else}
  <div class="empty">加载中...</div>
{/if}

<!-- Provider Modal -->
{#if showModal}
  <div class="modal-overlay" role="dialog" onclick={(e) => { if (e.target === e.currentTarget) showModal = false }}>
    <div class="modal">
      <h2>{editingIdx >= 0 ? '编辑' : '添加'} Provider</h2>
      <div class="form-row">
        <div class="form-group">
          <label>名称</label>
          <input bind:value={form.name} disabled={editingIdx >= 0} placeholder="my-provider" />
        </div>
        <div class="form-group">
          <label>类型</label>
          <select bind:value={form.type}>
            <option value="anthropic">anthropic</option>
            <option value="openai">openai</option>
          </select>
        </div>
      </div>
      <div class="form-group">
        <label>Base URL</label>
        <input bind:value={form.base_url} placeholder="https://api.example.com/v1/messages" />
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>API Key {editingIdx >= 0 ? '（留空保持不变）' : ''}</label>
          <input type="password" bind:value={form.api_key} placeholder="sk-..." />
        </div>
        <div class="form-group">
          <label>认证方式</label>
          <select bind:value={form.auth_scheme}>
            <option value="x-api-key">x-api-key</option>
            <option value="bearer">bearer</option>
          </select>
        </div>
      </div>
      <div class="form-group">
        <label>模型</label>
        <div style="display: flex; gap: 6px; margin-bottom: 6px;">
          <input
            bind:value={formModelInput}
            placeholder="输入模型名后回车或点击添加"
            onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addModel() } }}
            style="flex: 1;"
          />
          <button type="button" onclick={addModel}>添加</button>
        </div>
        {#if form.models.length > 0}
          <div style="display: flex; flex-wrap: wrap; gap: 4px;">
            {#each form.models as m}
              <span class="model-chip {form.type === 'openai' ? 'chip-openai' : 'chip-anthropic'}" style="display: inline-flex; align-items: center; gap: 4px; border-radius: 4px; padding: 2px 8px; font-size: 12px; font-family: monospace;">
                {m}
                <button type="button" onclick={() => { form.models = form.models.filter(x => x !== m) }} style="background: none; border: none; cursor: pointer; color: var(--red); padding: 0; font-size: 14px; line-height: 1;">×</button>
              </span>
            {/each}
          </div>
        {:else}
          <div style="font-size: 11px; color: var(--sidebar-text);">暂无模型，请在上方添加</div>
        {/if}
      </div>
      <div class="form-group">
        <label>超时（秒）</label>
        <input type="number" bind:value={form.timeout} />
      </div>
      <div class="form-group">
        <label>优先级（越小越高）</label>
        <input type="number" bind:value={form.priority} />
      </div>
      <div class="form-group">
        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer;">
          <input type="checkbox" bind:checked={form.enabled} />
          启用参与路由
        </label>
        <div style="font-size: 11px; color: var(--sidebar-text); margin-top: 2px;">停用后不参与路由 fallback 链</div>
      </div>
      <div class="modal-actions">
        <button onclick={() => showModal = false}>取消</button>
        <button class="btn-primary" onclick={saveProvider}>确定</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .toggle-switch {
    position: relative;
    display: inline-block;
    width: 36px;
    height: 18px;
    cursor: pointer;
  }
  .toggle-switch input { opacity: 0; width: 0; height: 0; }
  .toggle-slider {
    position: absolute;
    inset: 0;
    background: var(--sidebar-border);
    border-radius: 9px;
    transition: background 0.2s;
  }
  .toggle-switch input:disabled + .toggle-slider { opacity: 0.4; cursor: not-allowed; }
  .toggle-slider::before {
    content: '';
    position: absolute;
    height: 12px;
    width: 12px;
    left: 3px;
    bottom: 3px;
    background: white;
    border-radius: 50%;
    transition: transform 0.2s;
  }
  .toggle-switch input:checked + .toggle-slider { background: var(--green); }
  .toggle-switch input:checked + .toggle-slider::before { transform: translateX(18px); }
</style>

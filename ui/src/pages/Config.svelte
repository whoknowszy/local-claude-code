<script>
  import { api } from '../api.js'

  let config = $state(null)
  let error = $state('')
  let saved = $state(false)

  // Provider modal state
  let showModal = $state(false)
  let editingIdx = $state(-1)  // -1 = create, >= 0 = edit
  let form = $state({
    name: '', type: 'anthropic', base_url: '', api_key: '',
    auth_scheme: 'x-api-key', models_text: '', timeout: 600,
  })

  let routeOptions = $derived.by(() => {
    if (!config?.providers) return []
    const opts = []
    for (const p of config.providers) {
      for (const m of (p.models || [])) {
        opts.push(`${p.name},${m}`)
      }
    }
    return opts
  })

  async function load() {
    try {
      config = await api.getConfig(true)
    } catch (e) {
      error = e.message
    }
  }

  $effect(() => { load() })

  function openCreate() {
    editingIdx = -1
    form = { name: '', type: 'anthropic', base_url: '', api_key: '', auth_scheme: 'x-api-key', models_text: '', timeout: 600 }
    showModal = true
  }

  function openEdit(idx) {
    const p = config.providers[idx]
    editingIdx = idx
    form = {
      name: p.name, type: p.type, base_url: p.base_url,
      api_key: '',
      auth_scheme: p.auth_scheme || 'x-api-key',
      models_text: (p.models || []).join('\n'),
      timeout: p.timeout || 600,
    }
    showModal = true
  }

  function saveProvider() {
    const provider = {
      name: form.name,
      type: form.type,
      base_url: form.base_url,
      auth_scheme: form.auth_scheme,
      models: form.models_text.split('\n').map(s => s.trim()).filter(Boolean),
      timeout: form.timeout,
    }
    if (form.api_key) provider.api_key = form.api_key

    if (editingIdx >= 0) {
      // Keep existing api_key if not changed
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

  async function save() {
    error = ''
    saved = false
    try {
      await api.updateConfig(config)
      saved = true
      setTimeout(() => saved = false, 2000)
    } catch (e) {
      error = e.message
    }
  }
</script>

<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
  <h2>配置</h2>
</div>

{#if error}
  <div class="card" style="color: var(--red)">{error}</div>
{/if}
{#if saved}
  <div class="card" style="color: var(--green)">配置已保存！</div>
{/if}

{#if config}
  <!-- Server -->
  <div class="card">
    <h2>服务器</h2>
    <div class="form-row">
      <div class="form-group">
        <label>Host</label>
        <input bind:value={config.server.host} />
      </div>
      <div class="form-group">
        <label>Port</label>
        <input type="number" bind:value={config.server.port} />
      </div>
      <div class="form-group">
        <label>代理 API Key（可选）</label>
        <input bind:value={config.server.api_key} placeholder="留空则不启用代理认证" />
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
                  // Keep the most verbose level as the primary (for structlog filtering)
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
        <input bind:value={config.logging.log_dir} placeholder="~/.lccg/logs" />
      </div>
    </div>
  </div>

  <!-- Providers -->
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <h2 style="margin-bottom: 0;">Providers</h2>
      <button class="btn-primary" onclick={openCreate}>+ 添加 Provider</button>
    </div>
    {#if config.providers.length === 0}
      <div class="empty">暂无 Provider</div>
    {:else}
      <table>
        <thead>
          <tr>
            <th>名称</th>
            <th>类型</th>
            <th>Base URL</th>
            <th>模型</th>
            <th>认证</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {#each config.providers as p, idx}
            <tr>
              <td><strong>{p.name}</strong></td>
              <td><span class="badge badge-blue">{p.type}</span></td>
              <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis;">{p.base_url}</td>
              <td>{(p.models || []).join(', ')}</td>
              <td>{p.auth_scheme}</td>
              <td class="actions">
                <button onclick={() => openEdit(idx)}>编辑</button>
                <button class="btn-danger" onclick={() => removeProvider(idx)}>删除</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <!-- Router -->
  <div class="card">
    <h2>路由</h2>
    <div class="form-group">
      <label>默认路由</label>
      <select bind:value={config.router.default}>
        <option value="">-- 不设置 --</option>
        {#each routeOptions as opt}
          <option value={opt}>{opt}</option>
        {/each}
      </select>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label>后台任务路由</label>
        <select bind:value={config.router.background}>
          <option value="">-- 不设置 --</option>
          {#each routeOptions as opt}
            <option value={opt}>{opt}</option>
          {/each}
        </select>
      </div>
      <div class="form-group">
        <label>思考路由</label>
        <select bind:value={config.router.think}>
          <option value="">-- 不设置 --</option>
          {#each routeOptions as opt}
            <option value={opt}>{opt}</option>
          {/each}
        </select>
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label>长上下文路由</label>
        <select bind:value={config.router.long_context}>
          <option value="">-- 不设置 --</option>
          {#each routeOptions as opt}
            <option value={opt}>{opt}</option>
          {/each}
        </select>
      </div>
      <div class="form-group">
        <label>长上下文阈值（tokens）</label>
        <input type="number" bind:value={config.router.long_context_threshold} />
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label>网页搜索路由</label>
        <select bind:value={config.router.web_search}>
          <option value="">-- 不设置 --</option>
          {#each routeOptions as opt}
            <option value={opt}>{opt}</option>
          {/each}
        </select>
      </div>
      <div class="form-group">
        <label>故障回退路由</label>
        <select bind:value={config.router.fallback}>
          <option value="">-- 不设置 --</option>
          {#each routeOptions as opt}
            <option value={opt}>{opt}</option>
          {/each}
        </select>
      </div>
    </div>
  </div>

  <button class="btn-primary" onclick={save} style="margin-top: 8px;">保存全部配置</button>
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
        <label>模型（每行一个）</label>
        <textarea bind:value={form.models_text} rows="3" placeholder="model-1&#10;model-2"></textarea>
      </div>
      <div class="form-group">
        <label>超时（秒）</label>
        <input type="number" bind:value={form.timeout} />
      </div>
      <div class="modal-actions">
        <button onclick={() => showModal = false}>取消</button>
        <button class="btn-primary" onclick={saveProvider}>确定</button>
      </div>
    </div>
  </div>
{/if}

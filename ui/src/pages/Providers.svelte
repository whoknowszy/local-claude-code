<script>
  import { api } from '../api.js'

  let providers = $state([])
  let showModal = $state(false)
  let editing = $state(null)  // null = create, object = edit
  let error = $state('')

  // Form state
  let form = $state({
    name: '', type: 'anthropic', base_url: '', api_key: '',
    auth_scheme: 'x-api-key', models_text: '', timeout: 600,
  })

  async function load() {
    try {
      providers = await api.getProviders()
    } catch (e) {
      error = e.message
    }
  }

  $effect(() => { load() })

  function openCreate() {
    editing = null
    form = { name: '', type: 'anthropic', base_url: '', api_key: '', auth_scheme: 'x-api-key', models_text: '', timeout: 600 }
    showModal = true
  }

  function openEdit(p) {
    editing = p
    form = {
      name: p.name, type: p.type, base_url: p.base_url,
      api_key: '',  // don't pre-fill masked key
      auth_scheme: p.auth_scheme || 'x-api-key',
      models_text: (p.models || []).join('\n'),
      timeout: p.timeout || 600,
    }
    showModal = true
  }

  async function save() {
    const payload = {
      name: form.name,
      type: form.type,
      base_url: form.base_url,
      auth_scheme: form.auth_scheme,
      models: form.models_text.split('\n').map(s => s.trim()).filter(Boolean),
      timeout: form.timeout,
    }
    if (form.api_key) payload.api_key = form.api_key

    try {
      if (editing) {
        await api.updateProvider(editing.name, payload)
      } else {
        await api.createProvider(payload)
      }
      showModal = false
      await load()
    } catch (e) {
      error = e.message
    }
  }

  async function remove(name) {
    if (!confirm(`Delete provider "${name}"?`)) return
    try {
      await api.deleteProvider(name)
      await load()
    } catch (e) {
      error = e.message
    }
  }
</script>

<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
  <h2>Providers</h2>
  <button class="btn-primary" onclick={openCreate}>+ Add Provider</button>
</div>

{#if error}
  <div class="card" style="color: var(--red)">{error} <button onclick={() => error = ''}>dismiss</button></div>
{/if}

<div class="card">
  {#if providers.length === 0}
    <div class="empty">No providers configured</div>
  {:else}
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Type</th>
          <th>Base URL</th>
          <th>Models</th>
          <th>Auth</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {#each providers as p}
          <tr>
            <td><strong>{p.name}</strong></td>
            <td><span class="badge badge-blue">{p.type}</span></td>
            <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis;">{p.base_url}</td>
            <td>{(p.models || []).join(', ')}</td>
            <td>{p.auth_scheme}</td>
            <td class="actions">
              <button onclick={() => openEdit(p)}>Edit</button>
              <button class="btn-danger" onclick={() => remove(p.name)}>Delete</button>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

{#if showModal}
  <div class="modal-overlay" onclick={(e) => { if (e.target === e.currentTarget) showModal = false }}>
    <div class="modal">
      <h2>{editing ? 'Edit' : 'Add'} Provider</h2>
      <div class="form-row">
        <div class="form-group">
          <label>Name</label>
          <input bind:value={form.name} disabled={!!editing} placeholder="my-provider" />
        </div>
        <div class="form-group">
          <label>Type</label>
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
          <label>API Key {editing ? '(leave empty to keep current)' : ''}</label>
          <input type="password" bind:value={form.api_key} placeholder="sk-..." />
        </div>
        <div class="form-group">
          <label>Auth Scheme</label>
          <select bind:value={form.auth_scheme}>
            <option value="x-api-key">x-api-key</option>
            <option value="bearer">bearer</option>
          </select>
        </div>
      </div>
      <div class="form-group">
        <label>Models (one per line)</label>
        <textarea bind:value={form.models_text} rows="3" placeholder="model-1&#10;model-2"></textarea>
      </div>
      <div class="form-group">
        <label>Timeout (seconds)</label>
        <input type="number" bind:value={form.timeout} />
      </div>
      <div class="modal-actions">
        <button onclick={() => showModal = false}>Cancel</button>
        <button class="btn-primary" onclick={save}>Save</button>
      </div>
    </div>
  </div>
{/if}

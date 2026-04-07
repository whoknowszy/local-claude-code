<script>
  import { api } from '../api.js'

  let providers = $state([])
  let selectedProvider = $state('')
  let selectedModel = $state('')
  let message = $state('Hello, what model are you?')
  let result = $state(null)
  let loading = $state(false)
  let error = $state('')

  $effect(() => {
    api.getProviders().then(p => providers = p).catch(e => error = e.message)
  })

  let models = $derived(
    providers.find(p => p.name === selectedProvider)?.models || []
  )

  async function send() {
    if (!selectedProvider || !selectedModel || !message.trim()) return
    loading = true
    result = null
    error = ''
    try {
      const provider = providers.find(p => p.name === selectedProvider)
      const res = await fetch(provider.base_url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(provider.auth_scheme === 'bearer'
            ? { 'Authorization': `Bearer ${provider.api_key}` }
            : { 'x-api-key': provider.api_key }),
        },
        body: JSON.stringify({
          model: selectedModel,
          max_tokens: 256,
          messages: [{ role: 'user', content: message }],
        }),
      })
      result = await res.json()
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }
</script>

<h2>Test Provider</h2>

<div class="card">
  <div class="form-row">
    <div class="form-group">
      <label>Provider</label>
      <select bind:value={selectedProvider}>
        <option value="">-- select --</option>
        {#each providers as p}
          <option value={p.name}>{p.name} ({p.type})</option>
        {/each}
      </select>
    </div>
    <div class="form-group">
      <label>Model</label>
      <select bind:value={selectedModel}>
        <option value="">-- select --</option>
        {#each models as m}
          <option value={m}>{m}</option>
        {/each}
      </select>
    </div>
  </div>
  <div class="form-group">
    <label>Message</label>
    <textarea bind:value={message} rows="3"></textarea>
  </div>
  <button class="btn-primary" onclick={send} disabled={loading || !selectedProvider || !selectedModel}>
    {loading ? 'Sending...' : 'Send Test'}
  </button>
</div>

{#if error}
  <div class="card" style="color: var(--red)">Error: {error}</div>
{/if}

{#if result}
  <div class="card">
    <h2>Response</h2>
    <pre>{JSON.stringify(result, null, 2)}</pre>
  </div>
{/if}

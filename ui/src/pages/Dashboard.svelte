<script>
  import { api } from '../api.js'

  let stats = $state(null)
  let error = $state('')

  async function load() {
    try {
      stats = await api.getStats()
    } catch (e) {
      error = e.message
    }
  }

  $effect(() => {
    load()
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  })

  function formatUptime(seconds) {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    return h > 0 ? `${h}时${m}分` : `${m}分`
  }
</script>

<h2>仪表盘</h2>

{#if error}
  <div class="card" style="color: var(--red)">{error}</div>
{:else if stats}
  {@const s = stats.summary}

  <!-- 概览卡片 -->
  <div class="stat-grid">
    <div class="stat-card">
      <div class="label">总请求数</div>
      <div class="value">{s.total_requests}</div>
    </div>
    <div class="stat-card">
      <div class="label">成功率</div>
      <div class="value">{s.total_requests > 0 ? Math.round(s.success / s.total_requests * 100) : 100}%</div>
    </div>
    <div class="stat-card">
      <div class="label">平均延迟</div>
      <div class="value">{s.avg_latency_ms}ms</div>
    </div>
    <div class="stat-card">
      <div class="label">运行时间</div>
      <div class="value">{formatUptime(s.uptime_seconds)}</div>
    </div>
    <div class="stat-card">
      <div class="label">输入 Tokens</div>
      <div class="value">{s.total_input_tokens.toLocaleString()}</div>
    </div>
    <div class="stat-card">
      <div class="label">输出 Tokens</div>
      <div class="value">{s.total_output_tokens.toLocaleString()}</div>
    </div>
  </div>

  <!-- Provider 统计 + 最近请求 并排 -->
  <div class="dashboard-panels">
    {#if Object.keys(stats.providers).length > 0}
      <div class="card">
        <h2>Provider 统计</h2>
        <table>
          <thead>
            <tr>
              <th>Provider</th>
              <th>总数</th>
              <th>成功</th>
              <th>失败</th>
              <th>输入 Tokens</th>
              <th>输出 Tokens</th>
              <th>平均延迟</th>
            </tr>
          </thead>
          <tbody>
            {#each Object.entries(stats.providers) as [name, p]}
              <tr>
                <td>{name}</td>
                <td>{p.total}</td>
                <td style="color: var(--green)">{p.success}</td>
                <td style="color: var(--red)">{p.error}</td>
                <td>{p.total_input_tokens.toLocaleString()}</td>
                <td>{p.total_output_tokens.toLocaleString()}</td>
                <td>{p.avg_latency_ms}ms</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    {#if stats.recent.length > 0}
      <div class="card">
        <h2>最近请求</h2>
        <table>
          <thead>
            <tr>
              <th>状态</th>
              <th>Provider</th>
              <th>模型</th>
              <th>延迟</th>
              <th>输入</th>
              <th>输出</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            {#each stats.recent as r}
              <tr>
                <td>
                  <span class="badge {r.status === 'success' ? 'badge-green' : 'badge-red'}">{r.status === 'success' ? '成功' : '失败'}</span>
                </td>
                <td>{r.provider}</td>
                <td>{r.model}</td>
                <td>{r.latency_ms}ms</td>
                <td>{r.input_tokens}</td>
                <td>{r.output_tokens}</td>
                <td style="color: var(--red)">{r.error ? r.error.slice(0, 50) : ''}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
{:else}
  <div class="empty">加载中...</div>
{/if}

<script>
  let { page = '/' } = $props()
</script>

<nav class="sidebar">
  <h1>LCCG Gateway</h1>
  <a href="#/" class:active={page === '/'}>仪表盘</a>
  <a href="#/config" class:active={page === '/config'}>配置</a>
  <a href="#/logs" class:active={page === '/logs'}>日志</a>
  <a href="#/test" class:active={page === '/test'}>测试</a>
</nav>

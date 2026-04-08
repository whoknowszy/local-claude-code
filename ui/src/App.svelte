<script>
  import './app.css'
  import Nav from './components/Nav.svelte'
  import Dashboard from './pages/Dashboard.svelte'
  import Config from './pages/Config.svelte'
  import Logs from './pages/Logs.svelte'

  let page = $state(window.location.hash.slice(1) || '/')

  window.addEventListener('hashchange', () => {
    page = window.location.hash.slice(1) || '/'
  })

  const pages = {
    '/': Dashboard,
    '/config': Config,
    '/logs': Logs,
  }

  let CurrentPage = $derived(pages[page] || Dashboard)
</script>

<div class="app-root">
  <Nav {page} />
  <div class="content">
    <div class="page-inner">
      <CurrentPage />
    </div>
  </div>
</div>

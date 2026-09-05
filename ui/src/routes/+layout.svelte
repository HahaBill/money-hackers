<script lang="ts">
  import '@fontsource-variable/atkinson-hyperlegible-next';
  import '@fontsource/atkinson-hyperlegible-mono/400.css';
  import '@fontsource/atkinson-hyperlegible-mono/700.css';
  import '$lib/tokens.css';
  import AnalystDock from '$lib/components/AnalystDock.svelte';
  import Logo from '$lib/components/Logo.svelte';
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { loadDashboard } from '$lib/api/report';

  let { children } = $props();
  let railHidden = $state(false);

  const desktopNav = [
    { label: 'Workbook', href: '/month', icon: '▦' },
    { label: 'Today', href: '/today', icon: '◷' },
    { label: 'Capture', href: '/capture', icon: '▤' },
    { label: 'Audit trail', href: '/audit', icon: '⌁' },
    { label: 'Settings', href: '/settings', icon: '⚙' }
  ];
  const active = (href: string) => page.url.pathname === href || page.url.pathname.startsWith(`${href}/`);

  onMount(() => {
    const theme = localStorage.getItem('till-theme');
    if (theme === 'light' || theme === 'dark') document.documentElement.dataset.theme = theme;
    railHidden = localStorage.getItem('till-sidebar') === 'hidden';
    loadDashboard();
  });

  function toggleRail() {
    railHidden = !railHidden;
    localStorage.setItem('till-sidebar', railHidden ? 'hidden' : 'open');
  }
</script>

<svelte:head>
  <title>Till · Financial analyst</title>
  <meta
    name="description"
    content="A traceable financial analyst for independent cafés."
  />
</svelte:head>

<div class:rail-hidden={railHidden} class="app-shell">
  <aside class="rail" aria-label="Workspace sidebar" aria-hidden={railHidden} inert={railHidden}>
    <div class="rail-top">
      <a href="/month" class="rail-logo"><Logo /></a>
      <button class="rail-toggle" onclick={toggleRail} aria-label="Hide sidebar">‹</button>
    </div>
    <nav aria-label="Primary navigation">
      {#each desktopNav as item}
        <a href={item.href} class:active={active(item.href)} aria-current={active(item.href) ? 'page' : undefined}>
          <span class="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}
        </a>
      {/each}
    </nav>
    <span class="business">Garden State Coffee</span>
  </aside>

  {#if railHidden}
    <button class="rail-restore" onclick={toggleRail} aria-label="Show sidebar">☰</button>
  {/if}

  <main>{@render children()}</main>
  <AnalystDock />
</div>

<style>
  .app-shell {
    min-height: 100vh;
  }

  main {
    min-width: 0;
    margin-left: var(--rail);
    transition: margin-left 160ms ease;
  }

  .rail-hidden main {
    margin-left: 0;
  }

  .rail {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 20;
    display: flex;
    width: var(--rail);
    flex-direction: column;
    padding: 2rem 1rem 1.5rem;
    background: var(--chalk);
    color: var(--paper);
    transition: transform 160ms ease;
  }

  .rail-hidden .rail {
    transform: translateX(-100%);
  }

  .rail-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .rail-logo {
    padding: 0.2rem 0 1.8rem 1rem;
  }

  .rail-toggle,
  .rail-restore {
    display: grid;
    place-items: center;
    border: 1px solid color-mix(in srgb, var(--paper) 28%, transparent);
    color: var(--paper);
  }

  .rail-toggle {
    width: 2rem;
    min-height: 2rem;
    padding: 0;
  }

  .rail-restore {
    position: fixed;
    top: 1rem;
    left: 1rem;
    z-index: 65;
    width: 2.6rem;
    min-height: 2.6rem;
    border-color: var(--line);
    background: var(--white);
    color: var(--chalk);
    box-shadow: 0 0.25rem 1rem color-mix(in srgb, var(--chalk) 10%, transparent);
  }

  .rail nav {
    display: grid;
    gap: 0.25rem;
  }

  .rail nav a {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    border-radius: 0.4rem;
    padding: 0.65rem 1rem;
    font-size: 1.05rem;
  }

  .nav-icon {
    display: grid;
    width: 1.25rem;
    place-items: center;
    color: color-mix(in srgb, var(--paper) 75%, transparent);
    font-family: var(--font-mono);
    font-size: 1rem;
  }

  .rail nav a:hover,
  .rail nav a.active {
    background: color-mix(in srgb, var(--paper) 14%, transparent);
  }

  .rail nav a.active {
    font-weight: 700;
  }

  .business {
    margin-top: auto;
    padding: 0 1rem;
    color: color-mix(in srgb, var(--paper) 60%, transparent);
    font-size: 0.8rem;
  }

</style>

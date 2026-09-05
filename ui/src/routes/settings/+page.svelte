<script lang="ts">
  import { onMount } from 'svelte';
  let theme = $state<'system' | 'light' | 'dark'>('system');

  onMount(() => {
    theme = (localStorage.getItem('till-theme') as typeof theme) || 'system';
  });

  function setTheme(next: typeof theme) {
    theme = next;
    localStorage.setItem('till-theme', next);
    if (next === 'system') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.dataset.theme = next;
  }
</script>

<div class="page settings-page">
  <header class="page-header"><div><h1>Settings</h1><p class="muted">Business and device preferences</p></div></header>
  <section class="card">
    <h2>Business</h2>
    <label>Display name<input value="Garden State Coffee" disabled /></label>
    <p class="muted">Business configuration comes from the backend environment.</p>
  </section>
  <section class="card">
    <h2>Appearance</h2>
    <div class="theme-buttons">
      {#each ['system', 'light', 'dark'] as option}
        <button class:active={theme === option} onclick={() => setTheme(option as typeof theme)}>{option}</button>
      {/each}
    </div>
    <p class="muted">Phone uses the system’s late-night dark appearance by default.</p>
  </section>
  <section class="card">
    <h2>Data boundary</h2>
    <p>Financial arithmetic, confidence, and simulations come from the FastAPI backend. This browser only presents and collects owner input.</p>
  </section>
</div>

<style>
  .settings-page { width: min(100%, 52rem); }
  section + section { margin-top: 1rem; }
  label { display: grid; gap: 0.35rem; }
  input { min-height: 2.75rem; border: 1px solid var(--line); border-radius: 0.4rem; background: var(--soft); padding: 0.5rem 0.7rem; color: var(--chalk); }
  .theme-buttons { display: flex; gap: 0.5rem; }
  .theme-buttons button { text-transform: capitalize; }
  .theme-buttons button.active { border-color: var(--awning); background: var(--awning); color: white; }
</style>

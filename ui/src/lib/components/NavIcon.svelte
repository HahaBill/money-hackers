<script lang="ts">
  let { name }: { name: 'workbook' | 'today' | 'capture' | 'audit' | 'settings' } = $props();
</script>

<svg viewBox="0 0 24 24" aria-hidden="true">
  {#if name === 'workbook'}
    <rect x="3.5" y="4" width="17" height="16" rx="2"></rect>
    <path d="M3.5 9h17M9 4v16M15 4v16"></path>
  {:else if name === 'today'}
    <circle cx="12" cy="12" r="8.5"></circle>
    <path d="M12 7.5V12l3.2 2"></path>
  {:else if name === 'capture'}
    <rect x="4" y="3.5" width="16" height="17" rx="2"></rect>
    <path d="M8 8h8M8 12h8M8 16h5"></path>
  {:else if name === 'audit'}
    <path d="M5 7.5h6M5 12h9M5 16.5h6"></path>
    <circle cx="17" cy="7.5" r="2"></circle>
    <circle cx="18" cy="16.5" r="2"></circle>
  {:else}
    <circle cx="12" cy="12" r="3"></circle>
    <path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2M6 6l1.4 1.4M16.6 16.6 18 18M18 6l-1.4 1.4M7.4 16.6 6 18"></path>
  {/if}
</svg>

<style>
  svg {
    width: 1.05rem;
    height: 1.05rem;
    fill: none;
    stroke: currentColor;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-width: 1.55;
  }
</style>

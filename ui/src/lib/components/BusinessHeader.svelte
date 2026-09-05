<script lang="ts">
  import Logo from './Logo.svelte';
  let {
    business,
    subtitle,
    compact = false
  }: { business: string; subtitle: string; compact?: boolean } = $props();
</script>

<header class:compact>
  <div class="identity">
    <Logo compact />
    <div>
      <strong>{business}</strong>
      <span>{subtitle}</span>
    </div>
  </div>
  <button class="avatar" aria-label="Open profile and settings">D</button>
</header>

<style>
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .identity {
    display: flex;
    align-items: center;
    gap: 0.65rem;
  }

  .identity div {
    display: grid;
  }

  strong {
    font-size: 1.05rem;
  }

  span {
    color: var(--muted);
    font-size: 0.92rem;
  }

  .avatar {
    display: grid;
    width: 2.8rem;
    min-height: 2.8rem;
    place-items: center;
    border: 0;
    border-radius: 50%;
    padding: 0;
    background: var(--chalk);
    color: var(--paper);
  }

  @media (min-width: 48rem) {
    header.compact .identity :global(svg) {
      display: none;
    }
  }
</style>

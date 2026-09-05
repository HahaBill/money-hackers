<script lang="ts">
  let { compact = false }: { compact?: boolean } = $props();
</script>

<span class="logo" aria-label="Till">
  <svg viewBox="0 0 42 36" aria-hidden="true">
    <path class="shop" d="M7 14h21v17H7z" />
    <path class="awning" d="M5 12h25" />
    <path class="stripe" d="M11 12v5m7-5v5m7-5v5" />
    <path class="door" d="M11 21h6v10h-6z" />
    <path class="trend" d="m26 10 4-4 3 3 5-7m-5 0h5v5" />
  </svg>
  {#if !compact}<strong>Till</strong>{/if}
</span>

<style>
  .logo {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
  }

  svg {
    width: 2.1rem;
    height: 1.8rem;
  }

  strong {
    font-size: 1.45rem;
    letter-spacing: -0.02em;
  }

  .shop {
    fill: currentColor;
  }

  .awning {
    fill: none;
    stroke: var(--awning);
    stroke-width: 4;
    stroke-linecap: round;
  }

  .stripe,
  .door {
    fill: none;
    stroke: var(--paper);
    stroke-width: 3;
  }

  .trend {
    fill: none;
    stroke: var(--stonks);
    stroke-width: 3;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
</style>

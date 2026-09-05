<script lang="ts">
  let { compact = false }: { compact?: boolean } = $props();
</script>

<span class="logo" aria-label="Larry">
  <span class="mark" aria-hidden="true"><b>L</b><i>✦</i></span>
  {#if !compact}<strong>Larry</strong>{/if}
</span>

<style>
  .logo {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
  }

  .mark {
    position: relative;
    display: grid;
    width: 1.75rem;
    height: 1.75rem;
    place-items: center;
    border-radius: 0.48rem;
    background: var(--chalk);
    color: white;
    box-shadow: 0 1px 2px color-mix(in srgb, black 18%, transparent);
  }

  .mark b {
    font-size: 0.95rem;
    font-weight: 700;
    line-height: 1;
  }

  .mark i {
    position: absolute;
    top: -0.27rem;
    right: -0.22rem;
    color: var(--awning);
    font-size: 0.6rem;
    font-style: normal;
    text-shadow: 0 0 0.18rem white;
  }

  strong {
    font-size: 1.1rem;
    font-weight: 680;
    letter-spacing: -0.025em;
  }
</style>

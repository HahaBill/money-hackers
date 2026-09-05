<script lang="ts">
  let {
    value = $bindable<'receipt' | 'sheet'>()
  }: { value: 'receipt' | 'sheet' } = $props();
</script>

<div class="toggle" aria-label="Month layout">
  <button class:active={value === 'receipt'} onclick={() => (value = 'receipt')}>Receipt</button>
  <button class:active={value === 'sheet'} onclick={() => (value = 'sheet')}>Sheet</button>
</div>

<style>
  .toggle {
    display: inline-grid;
    grid-template-columns: 1fr 1fr;
    border: 1px solid var(--chalk);
    border-radius: 0.45rem;
    overflow: hidden;
  }

  button {
    min-height: 2.25rem;
    border: 0;
    border-radius: 0;
    padding: 0.3rem 0.8rem;
  }

  button.active {
    background: var(--chalk);
    color: var(--paper);
  }
</style>

/* Embedded in the document: playback must not wait for the application bundle. */
(() => {
  let waiting = null;
  const hero = () => document.getElementById('teaser');
  function label() {
    const video = hero(), button = document.getElementById('hero-toggle');
    if (!video || !button) return;
    button.textContent = video.error ? 'Retry teaser' : video.paused ? 'Play teaser' : video.readyState < 3 ? 'Loading teaser…' : 'Pause teaser';
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.id === 'hero-toggle') {
      const video = hero();
      if (video.error) video.load();
      if (video.paused) video.play().catch(label); else video.pause();
      label();
      return;
    }
    if (!window.CLEAR_APP_READY && !button.closest('dialog')) {
      event.preventDefault(); event.stopImmediatePropagation();
      if (waiting) waiting.removeAttribute('aria-busy');
      waiting = button;
      button.setAttribute('aria-busy', 'true');
    }
  }, true);
  for (const type of ['playing', 'pause', 'waiting', 'error', 'loadeddata']) {
    document.addEventListener(type, event => { if (event.target.id === 'teaser') label(); }, true);
  }
  document.addEventListener('clear-app-ready', () => {
    if (!waiting) return;
    const button = waiting; waiting = null;
    button.removeAttribute('aria-busy'); button.click();
  });
})();

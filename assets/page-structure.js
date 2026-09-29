/* Deep links reveal details without recreating their players or losing playback state. */
(() => {
  const nav = document.querySelector('#page-contents'), toggle = document.querySelector('#contents-toggle');
  if (!nav || !toggle) return;
  const main = document.querySelector('#main'), links = [...nav.querySelectorAll('li>a')];
  const sections = links.map(link => ({link, node:document.getElementById(link.hash.slice(1))})).filter(s => s.node);
  let queued = false, lastActive;
  function menu(open) { if (open) { lastActive = null; schedule(); } toggle.setAttribute('aria-expanded', String(open)); nav.toggleAttribute('data-open', open); }
  toggle.onclick = () => menu(toggle.getAttribute('aria-expanded') !== 'true');
  function refresh() {
    queued = false;
    document.body.classList.toggle('reading-started', main.getBoundingClientRect().top < 100);
    const visible = sections.filter(s => s.node.getClientRects().length && !s.node.parentElement.closest('details:not([open])'));
    let active = visible[0];
    for (const s of visible) if (s.node.getBoundingClientRect().top <= 155) active = s;
    for (const s of sections) s.link.removeAttribute('aria-current');
    nav.querySelectorAll('[data-current-branch]').forEach(li => li.removeAttribute('data-current-branch'));
    if (active) {
      active.link.setAttribute('aria-current', 'location');
      if (lastActive !== active.link && nav.getClientRects().length) {
        const item = active.link.getBoundingClientRect(), rail = nav.getBoundingClientRect();
        if (item.bottom > rail.bottom - 16) nav.scrollTop += item.bottom - rail.bottom + 16;
        else if (item.top < rail.top + 30) nav.scrollTop += item.top - rail.top - 30;
        lastActive = active.link;
      }
      let li = active.link.parentElement;
      while (li && nav.contains(li)) { if (li.tagName === 'LI') li.setAttribute('data-current-branch', ''); li = li.parentElement; }
    }
  }
  function schedule() { if (!queued) { queued = true; requestAnimationFrame(refresh); } }
  function reveal(hash, focus = false) {
    const target = document.getElementById(hash.slice(1)); if (!target) return;
    let parent = target;
    while (parent) { if (parent.tagName === 'DETAILS') parent.open = true; parent = parent.parentElement; }
    requestAnimationFrame(() => {
      target.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block:'start'});
      if (focus) { if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1'); target.focus({preventScroll:true}); }
      schedule();
    });
  }
  document.addEventListener('click', e => {
    const a = e.target.closest('a[href^="#"]');
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || !document.getElementById(a.hash.slice(1))) return;
    e.preventDefault(); history.pushState(null, '', a.hash); menu(false); reveal(a.hash, true);
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && nav.hasAttribute('data-open')) { menu(false); toggle.focus(); } });
  document.addEventListener('pointerdown', e => { if (!nav.contains(e.target) && e.target !== toggle) menu(false); });
  document.addEventListener('toggle', schedule, true);
  window.addEventListener('scroll', schedule, {passive:true}); window.addEventListener('resize', schedule);
  window.addEventListener('hashchange', () => reveal(location.hash)); window.addEventListener('popstate', () => reveal(location.hash));
  new ResizeObserver(schedule).observe(main);
  if (location.hash) reveal(location.hash);
  refresh();
})();


;(() => {
  const sources = ${sources};
  const intervalMs = 2 * 60 * 1000;
  const fadeMs = 1400;
  const start = () => {
    const layers = [
      document.getElementById('cyberpunk-dynamic-background'),
      document.getElementById('cyberpunk-dynamic-background-next')
    ];
    if (layers.some(layer => !layer) || sources.length === 0) return;
    if (document.documentElement.classList.contains('compact-window')) return;
    let active = 0;
    let current = Math.floor(Math.random() * sources.length);
    const first = layers[active];
    first.src = sources[current];
    first.style.opacity = '1';
    first.play().catch(() => {});

    const rotate = () => {
      let next = current;
      if (sources.length > 1) {
        while (next === current) next = Math.floor(Math.random() * sources.length);
      }
      const incomingIndex = 1 - active;
      const incoming = layers[incomingIndex];
      const outgoing = layers[active];
      const reveal = () => {
        incoming.play().catch(() => {});
        incoming.style.opacity = '1';
        outgoing.style.opacity = '0';
        window.setTimeout(() => {
          outgoing.pause();
          outgoing.removeAttribute('src');
          outgoing.load();
          active = incomingIndex;
          current = next;
        }, fadeMs + 100);
      };
      incoming.style.opacity = '0';
      incoming.addEventListener('loadeddata', reveal, { once: true });
      incoming.src = sources[next];
      incoming.load();
    };
    window.setInterval(rotate, intervalMs);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();

;(() => {
  const markReviewButtons = (root) => {
    const buttons = root.matches?.('button') ? [root] : root.querySelectorAll?.('button') || [];
    for (const button of buttons) {
      if (/^(Review|\u5ba1\u6838)$$/.test(button.textContent.trim())) {
        button.classList.add('cybercodex-review-action');
      }
    }
  };
  const start = () => {
    markReviewButtons(document.body);
    new MutationObserver((changes) => {
      for (const change of changes) {
        for (const node of change.addedNodes) {
          if (node.nodeType === 1) markReviewButtons(node);
        }
      }
    }).observe(document.body, { childList: true, subtree: true });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();

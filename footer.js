(function () {
  // For URLs like /tools/json-formatter/ the slug is the last non-empty segment
  const segments = location.pathname.replace(/\/$/, '').split('/').filter(Boolean);
  const slug = segments[segments.length - 1] || 'index';
  const base = '/' + segments.slice(0, -1).join('/') + '/'; // e.g. "/tools/"
  const GITHUB_REPO = 'https://github.com/schepens83/tools';

  // Record visit for search ranking
  try {
    const analytics = JSON.parse(localStorage.getItem('tools_analytics') || '[]');
    analytics.push({ slug, timestamp: Date.now() });
    if (analytics.length > 500) analytics.splice(0, analytics.length - 500);
    localStorage.setItem('tools_analytics', JSON.stringify(analytics));
  } catch (_) {}

  const footer = document.createElement('footer');
  footer.style.cssText = [
    'padding: 0.75rem 1rem',
    'margin-top: 2rem',
    'border-top: 1px solid #ddd',
    'font-size: 0.8rem',
    'color: #666',
    'font-family: sans-serif',
  ].join(';');

  const changesId = 'footer-changes-link';
  footer.innerHTML =
    `<a href="${base}">← Home</a> · ` +
    `<a href="${base}colophon.html#${slug}">About this tool</a> · ` +
    `<a href="${GITHUB_REPO}/blob/main/${slug}/index.html">View source</a> · ` +
    `<a href="${GITHUB_REPO}/commits/main/${slug}/index.html" id="${changesId}">Changes</a>`;

  document.body.appendChild(footer);

  fetch(base + 'dates.json')
    .then(function (r) { return r.json(); })
    .then(function (dates) {
      const date = dates[slug];
      if (date) {
        const a = document.getElementById(changesId);
        if (a) a.textContent = 'Changes (updated ' + date + ')';
      }
    })
    .catch(function () {});
})();

(function () {
  const script = document.querySelector('[data-tool-search]');
  if (!script) return;

  let tools = [];
  let analytics = [];

  try {
    analytics = JSON.parse(localStorage.getItem('tools_analytics') || '[]');
  } catch (_) {}

  function visitCount(slug) {
    return analytics.filter(function (v) { return v.slug === slug; }).length;
  }

  function score(tool, query) {
    const q = query.toLowerCase();
    let s = visitCount(tool.slug) * 0.5;
    if (tool.slug.startsWith(q)) s += 10;
    if (tool.title.toLowerCase().includes(q)) s += 5;
    if ((tool.description || '').toLowerCase().includes(q)) s += 2;
    return s;
  }

  function render(query) {
    const box = document.getElementById('tool-search-results');
    if (!query.trim()) { box.innerHTML = ''; return; }
    const q = query.toLowerCase();
    const results = tools
      .map(function (t) { return Object.assign({}, t, { _score: score(t, query) }); })
      .filter(function (t) {
        return t._score > 0 || t.slug.includes(q) || t.title.toLowerCase().includes(q);
      })
      .sort(function (a, b) { return b._score - a._score; })
      .slice(0, 12);
    box.innerHTML = results.map(function (t) {
      return '<li><a href="' + t.url + '">' + t.title + '</a>' +
        (t.description ? ' — ' + t.description : '') + '</li>';
    }).join('');
  }

  fetch('tools.json')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      tools = data;
      const h1 = document.querySelector('h1');
      if (!h1) return;
      const wrapper = document.createElement('div');
      wrapper.innerHTML =
        '<input id="tool-search" type="search" placeholder="Search tools…" ' +
        'aria-label="Search tools" autocomplete="off" ' +
        'style="font-size:1rem;padding:0.4rem 0.6rem;width:100%;max-width:360px;margin:0.75rem 0;box-sizing:border-box">' +
        '<ul id="tool-search-results" style="list-style:none;padding:0;margin:0"></ul>';
      h1.after(wrapper);

      const input = document.getElementById('tool-search');
      input.addEventListener('input', function (e) { render(e.target.value); });
      document.addEventListener('keydown', function (e) {
        if (e.key === '/' && document.activeElement !== input) {
          e.preventDefault();
          input.focus();
        }
      });
    })
    .catch(console.error);
})();

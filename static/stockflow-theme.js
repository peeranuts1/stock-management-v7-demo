/* STOCKFLOW V8 theme switcher; independent of language switcher */
(function () {
  'use strict';
  const KEY = 'stockflow_theme';
  const root = document.documentElement;
  const button = document.getElementById('sf-theme-toggle');
  if (!button) return;
  function storedTheme() { try { return localStorage.getItem(KEY); } catch (_) { return null; } }
  function setTheme(theme) {
    const next = theme === 'dark' ? 'dark' : 'light';
    root.setAttribute('data-theme', next);
    button.textContent = next === 'dark' ? '☀' : '☾';
    button.setAttribute('aria-pressed', String(next === 'dark'));
    button.setAttribute('aria-label', next === 'dark' ? 'Switch to light mode / เปลี่ยนเป็นโหมดสว่าง' : 'Switch to dark mode / เปลี่ยนเป็นโหมดมืด');
    button.title = button.getAttribute('aria-label');
    try { localStorage.setItem(KEY, next); } catch (_) {}
    document.dispatchEvent(new CustomEvent('stockflow:theme-changed', { detail: { theme: next } }));
  }
  const initial = storedTheme() === 'dark' ? 'dark' : 'light';
  setTheme(initial);
  button.addEventListener('click', function () { setTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'); });
})();

/* 연말정산 자가진단 (yearend-check.html)
   - 항목 14개는 build_yearend_check.py 가 data/yearend-check/<slug>.html 로 채워 넣는다.
     각 항목은 자기 <style>·<script> 를 가진 독립 블록이라 이 파일은 '어느 항목을 보여 줄지'만 다룬다.
   - 항목별 공유 주소: /yearend-check/<slug>  (서버가 미리보기 제목·설명을 그 항목으로 바꿔 준다)
     /yearend-check.html#<slug> 로 들어와도 그 항목을 연다. */
(function () {
  'use strict';

  var panes = document.querySelectorAll('.yc-pane');
  var navLinks = document.querySelectorAll('.yc-nav a[data-slug]');
  if (!panes.length) return;
  var slugs = Array.prototype.map.call(panes, function (p) { return p.getAttribute('data-slug'); });

  function itemUrl(slug) { return location.origin + '/yearend-check/' + encodeURIComponent(slug); }

  function open(slug, push, scroll) {
    if (slugs.indexOf(slug) === -1) slug = slugs[0];
    Array.prototype.forEach.call(panes, function (p) { p.hidden = p.getAttribute('data-slug') !== slug; });
    Array.prototype.forEach.call(navLinks, function (a) {
      var on = a.getAttribute('data-slug') === slug;
      a.classList.toggle('is-on', on);
      if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    if (push) {
      try { history.replaceState(null, '', '/yearend-check/' + encodeURIComponent(slug)); } catch (e) {}
    }
    if (scroll) {
      var nav = document.querySelector('.yc-nav');
      if (nav) nav.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  // 처음 열 항목: 서버가 심어 준 값(/yearend-check/<slug>) → #해시 → 첫 항목
  var m = location.pathname.match(/^\/yearend-check\/([A-Za-z0-9\-_]+)/);
  var first = window.__YC_OPEN || (m && m[1]) || (location.hash || '').replace('#', '') || slugs[0];
  open(first, false, false);

  Array.prototype.forEach.call(navLinks, function (a) {
    a.addEventListener('click', function (e) {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      open(a.getAttribute('data-slug'), true, false);
    });
  });

  /* ---------- 링크 복사 (카드뉴스와 같은 방식: 클립보드 → execCommand → prompt) ---------- */
  var toast = document.getElementById('ycToast');
  var toastTimer = null;
  function showToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('is-on'); }, 2200);
  }
  function legacyCopy(url) {
    var t = document.createElement('textarea');
    t.value = url;
    t.setAttribute('readonly', '');
    t.style.position = 'fixed'; t.style.top = '0'; t.style.left = '0'; t.style.opacity = '0';
    t.style.userSelect = 'text'; t.style.webkitUserSelect = 'text';
    document.body.appendChild(t);
    t.focus(); t.select(); t.setSelectionRange(0, url.length);
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(t);
    if (ok) showToast('링크를 복사했습니다');
    else window.prompt('아래 주소를 복사하세요', url);
  }
  function copyUrl(url) {
    if (navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext) {
      navigator.clipboard.writeText(url).then(function () { showToast('링크를 복사했습니다'); })
        .catch(function () { legacyCopy(url); });
    } else {
      legacyCopy(url);
    }
  }
  Array.prototype.forEach.call(document.querySelectorAll('.yc-copy[data-slug]'), function (b) {
    b.addEventListener('click', function () { copyUrl(itemUrl(b.getAttribute('data-slug'))); });
  });
})();

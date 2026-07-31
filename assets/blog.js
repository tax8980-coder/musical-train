/* =========================================================
   세무법인 지율 — 세무칼럼 (목록 blog.html / 본문 post.html)
   posts.json 기반. content_html 은 서버 빌드 시 이스케이프되어
   생성된 신뢰 가능한 HTML 입니다.
   ========================================================= */
(function () {
  'use strict';

  var $ = function (s, r) { return (r || document).querySelector(s); };

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function fmtDate(iso) {
    if (!iso) return '';
    var m = String(iso).match(/(\d{4})-(\d{2})-(\d{2})/);
    return m ? (m[1] + '.' + m[2] + '.' + m[3] + '.') : esc(iso);
  }
  function card(p) {
    var tags = (p.tags || []).map(function (t) {
      return '<span class="post-card__tag">' + esc(t) + '</span>';
    }).join('');
    var href = 'post.html?slug=' + encodeURIComponent(p.slug);
    return '<li class="post-card"><a class="post-card__link" href="' + href + '">' +
      (tags ? '<div class="post-card__tags">' + tags + '</div>' : '') +
      '<h3 class="post-card__title">' + esc(p.title) + '</h3>' +
      '<p class="post-card__summary">' + esc(p.summary) + '</p>' +
      '<div class="post-card__meta"><time datetime="' + esc(p.date) + '">' + fmtDate(p.date) + '</time>' +
      '<span class="post-card__go">읽기 <span aria-hidden="true">→</span></span></div></a></li>';
  }

  /* ---------------- 목록 페이지 ---------------- */
  var listEl = $('#blogList');
  if (listEl) {
    var PER_PAGE = 9;                 // 한 페이지당 칼럼 수 (3열 × 3행)
    var emptyEl = $('#blogEmpty');
    var tagFilter = $('#tagFilter');
    var tagListEl = $('#tagList');
    var searchEl = $('#blogSearch');
    var countEl = $('#blogCount');
    var pagerEl = $('#blogPager');
    var allPosts = [];
    var activeTag = '';
    var query = '';
    var page = 1;

    function filtered() {
      var q = query.trim().toLowerCase();
      return allPosts.filter(function (p) {
        if (activeTag && (p.tags || []).indexOf(activeTag) === -1) return false;
        if (!q) return true;
        var hay = ((p.title || '') + ' ' + (p.summary || '') + ' ' + (p.tags || []).join(' ')).toLowerCase();
        return hay.indexOf(q) !== -1;
      });
    }

    function pageWindow(cur, pages) {
      var out = [], i;
      if (pages <= 7) {
        for (i = 1; i <= pages; i++) out.push(i);
        return out;
      }
      var set = { 1: 1, 2: 1 };
      set[pages] = 1; set[pages - 1] = 1;
      set[cur] = 1; set[cur - 1] = 1; set[cur + 1] = 1;
      var nums = Object.keys(set).map(Number).filter(function (n) { return n >= 1 && n <= pages; }).sort(function (a, b) { return a - b; });
      var prev = 0;
      nums.forEach(function (n) {
        if (n - prev > 1) out.push('…');
        out.push(n);
        prev = n;
      });
      return out;
    }

    function renderPager(cur, pages) {
      if (!pagerEl) return;
      if (pages <= 1) { pagerEl.hidden = true; pagerEl.innerHTML = ''; return; }
      pagerEl.hidden = false;
      var html = [];
      html.push('<button type="button" class="pager__btn" data-page="' + (cur - 1) + '"' + (cur === 1 ? ' disabled' : '') + ' aria-label="이전 페이지">‹ 이전</button>');
      pageWindow(cur, pages).forEach(function (n) {
        if (n === '…') { html.push('<span class="pager__gap" aria-hidden="true">…</span>'); return; }
        html.push('<button type="button" class="pager__num' + (n === cur ? ' is-active" aria-current="page"' : '"') + ' data-page="' + n + '">' + n + '</button>');
      });
      html.push('<button type="button" class="pager__btn" data-page="' + (cur + 1) + '"' + (cur === pages ? ' disabled' : '') + ' aria-label="다음 페이지">다음 ›</button>');
      pagerEl.innerHTML = html.join('');
    }

    function render(keepScroll) {
      var posts = filtered();
      var total = posts.length;
      var pages = Math.max(1, Math.ceil(total / PER_PAGE));
      if (page > pages) page = pages;
      if (page < 1) page = 1;

      if (countEl) countEl.textContent = total ? ('총 ' + total + '편' + (query || activeTag ? ' (검색 결과)' : '')) : '';

      if (!total) {
        listEl.innerHTML = '';
        if (emptyEl) {
          emptyEl.hidden = false;
          emptyEl.textContent = (query || activeTag) ? '검색 결과가 없습니다.' : '아직 등록된 칼럼이 없습니다.';
        }
        renderPager(1, 1);
        return;
      }
      if (emptyEl) emptyEl.hidden = true;
      var start = (page - 1) * PER_PAGE;
      listEl.innerHTML = posts.slice(start, start + PER_PAGE).map(card).join('');
      renderPager(page, pages);
      if (!keepScroll && listEl.scrollIntoView) {
        listEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }

    function buildTags() {
      var set = {};
      allPosts.forEach(function (p) { (p.tags || []).forEach(function (t) { set[t] = (set[t] || 0) + 1; }); });
      var tags = Object.keys(set);
      if (!tags.length || !tagFilter) return;
      var chips = ['<button type="button" class="chip is-active" data-tag="">전체</button>'];
      tags.forEach(function (t) {
        chips.push('<button type="button" class="chip" data-tag="' + esc(t) + '">' + esc(t) + ' <span class="chip__n">' + set[t] + '</span></button>');
      });
      tagListEl.innerHTML = chips.join('');
      tagFilter.hidden = false;
      tagListEl.addEventListener('click', function (e) {
        var btn = e.target.closest('.chip');
        if (!btn) return;
        activeTag = btn.getAttribute('data-tag') || '';
        page = 1;
        Array.prototype.forEach.call(tagListEl.querySelectorAll('.chip'), function (c) {
          c.classList.toggle('is-active', c === btn);
        });
        render(true);
      });
    }

    if (searchEl) {
      searchEl.addEventListener('input', function () {
        query = searchEl.value || '';
        page = 1;
        render(true);
      });
    }
    if (pagerEl) {
      pagerEl.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-page]');
        if (!btn || btn.disabled) return;
        var n = parseInt(btn.getAttribute('data-page'), 10);
        if (!isNaN(n)) { page = n; render(); }
      });
    }

    fetch('/api/posts')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        allPosts = (data && data.posts) || [];
        if (!allPosts.length) { listEl.innerHTML = ''; if (emptyEl) emptyEl.hidden = false; return; }
        buildTags();
        render(true);
      })
      .catch(function () {
        listEl.innerHTML = '';
        if (emptyEl) { emptyEl.hidden = false; emptyEl.textContent = '칼럼을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'; }
      });
  }

  /* ---------------- 본문 페이지 ---------------- */
  var articleEl = $('#article');
  if (articleEl && !listEl) {
    var params = new URLSearchParams(location.search);
    var slug = params.get('slug') || '';
    var box = $('.container', articleEl);

    function fail(msg) {
      box.innerHTML = '<p class="article__error">' + esc(msg) + '</p>' +
        '<p><a class="btn btn--outline btn--sm" href="index.html">← 칼럼 목록으로</a></p>';
    }

    if (!slug) { fail('잘못된 접근입니다. 칼럼 목록에서 글을 선택해 주세요.'); return; }

    fetch('/api/posts/' + encodeURIComponent(slug))
      .then(function (r) {
        if (r.status === 404) throw new Error('not_found');
        return r.json();
      })
      .then(function (data) {
        var p = data && data.post;
        if (!p) throw new Error('no_post');

        document.title = p.title + ' | 세무 칼럼 · 세무법인 지율';
        var metaDesc = document.querySelector('meta[name="description"]');
        if (metaDesc && p.summary) metaDesc.setAttribute('content', p.summary);

        var tags = (p.tags || []).map(function (t) {
          return '<a class="post-card__tag" href="index.html">' + esc(t) + '</a>';
        }).join('');

        box.innerHTML =
          '<nav class="article__back"><a href="index.html">← 칼럼 목록</a></nav>' +
          '<header class="article__head">' +
          (tags ? '<div class="post-card__tags">' + tags + '</div>' : '') +
          '<h1 class="article__title">' + esc(p.title) + '</h1>' +
          '<div class="article__meta"><time datetime="' + esc(p.date) + '">' + fmtDate(p.date) + '</time>' +
          '<span class="article__author">세무법인 지율 · 손창용 세무사</span></div>' +
          '</header>' +
          '<div class="article__body prose">' + (p.content_html || '') + '</div>' +
          '<footer class="article__foot">' +
          '<a class="btn btn--outline btn--sm" href="index.html">← 칼럼 목록으로 바로 가기</a> ' +
          (p.source ? '<a class="btn btn--outline btn--sm" href="' + esc(p.source) + '" target="_blank" rel="noopener noreferrer">네이버 블로그에서 더 보기</a> ' : '') +
          '<a class="btn btn--primary btn--sm" href="contact.html">상담 문의하기</a>' +
          '</footer>';
        window.scrollTo(0, 0);
      })
      .catch(function (err) {
        if (String(err.message) === 'not_found') fail('요청하신 칼럼을 찾을 수 없습니다.');
        else fail('칼럼을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
      });
  }
})();

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
  function fmtViews(n) {
    n = parseInt(n, 10);
    if (isNaN(n) || n < 0) n = 0;
    try { return n.toLocaleString('ko-KR'); } catch (e) { return String(n); }
  }
  // 공개 조회수 노출 시작일: 2026-11-01. 그 전까지는 화면에 조회수를 숨긴다
  // (서버는 계속 누적). 이 날짜가 지나면 자동으로 표시된다. (월 인덱스 10 = 11월)
  var SHOW_VIEWS = new Date() >= new Date(2026, 10, 1);
  // 세목(첫 태그) → 제목 앞 이모지. server.py POST_TAG_EMOJI 와 동일하게 유지할 것.
  var TAG_EMOJI = { '법인세': '🏢', '소득세': '💰', '부가가치세': '🧾', '조세특례제한법': '🎯', '양도소득세': '🏠', '상속세': '👪', '증여세': '🎁', '취득세': '🏗️', '원천세': '💵', '연말정산': '🧮', '노동법': '👷', '지방세': '🏛️', '국세기본법': '⚖️', '4대보험': '🛡️' };
  function postEmoji(p) {
    var ts = p.tags || [];
    for (var i = 0; i < ts.length; i++) { if (TAG_EMOJI[ts[i]]) return TAG_EMOJI[ts[i]]; }
    return '📄';
  }
  function card(p) {
    var href = '/column/' + encodeURIComponent(p.slug) + '?from=all';
    var tagtxt = (p.tags || []).join(' · ');
    return '<li class="post-row"><a class="post-row__link" href="' + href + '">' +
      '<span class="post-row__title"><span class="post-row__emoji" aria-hidden="true">' + postEmoji(p) + '</span>' + esc(p.title) + '</span>' +
      '<span class="post-row__meta">' +
      (tagtxt ? '<span class="post-row__tags">' + esc(tagtxt) + '</span>' : '') +
      '<time class="post-row__date" datetime="' + esc(p.date) + '">' + fmtDate(p.date) + '</time>' +
      '</span></a></li>';
  }

  /* ---------------- 목록 페이지 ---------------- */
  var listEl = $('#blogList');
  if (listEl) {
    var PER_PAGE = 10;                // 한 페이지당 칼럼 수 (리스트형 10개씩)
    var emptyEl = $('#blogEmpty');
    var tagFilter = $('#tagFilter');
    var tagListEl = $('#tagList');
    var searchEl = $('#blogSearch');
    var countEl = $('#blogCount');
    var pagerEl = $('#blogPager');
    var quickWrap = $('#quickList');
    var quickEl = $('#quickTitles');
    var quickNav = $('#quickNav');
    var quickPageEl = $('#quickPage');
    var Q_PER = 5;
    var qPage = 1;
    var allPosts = [];
    var activeTag = '';
    var query = '';
    var page = 1;

    function renderQuick() {
      if (!quickEl) return;
      var total = allPosts.length;
      if (!total) { if (quickWrap) quickWrap.hidden = true; return; }
      if (quickWrap) quickWrap.hidden = false;
      var qPages = Math.max(1, Math.ceil(total / Q_PER));
      if (qPage > qPages) qPage = qPages;
      if (qPage < 1) qPage = 1;
      var start = (qPage - 1) * Q_PER;
      quickEl.innerHTML = allPosts.slice(start, start + Q_PER).map(function (p, i) {
        var href = '/column/' + encodeURIComponent(p.slug);
        return '<li class="quick-list__item"><a class="quick-list__link" href="' + href + '">' +
          '<span class="quick-list__no">' + (start + i + 1) + '</span>' +
          '<span class="quick-list__text">' + esc(p.title) + '</span>' +
          '<span class="quick-list__arrow" aria-hidden="true">→</span></a></li>';
      }).join('');
      if (quickNav) {
        if (qPages <= 1) { quickNav.hidden = true; }
        else {
          quickNav.hidden = false;
          if (quickPageEl) quickPageEl.textContent = qPage + ' / ' + qPages;
          var prev = quickNav.querySelector('[data-q="prev"]');
          var next = quickNav.querySelector('[data-q="next"]');
          if (prev) prev.disabled = qPage === 1;
          if (next) next.disabled = qPage === qPages;
        }
      }
    }

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
    if (quickNav) {
      quickNav.addEventListener('click', function (e) {
        var b = e.target.closest('[data-q]');
        if (!b || b.disabled) return;
        qPage += (b.getAttribute('data-q') === 'next' ? 1 : -1);
        renderQuick();
      });
    }

    fetch('/api/posts')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        allPosts = (data && data.posts) || [];
        if (!allPosts.length) { listEl.innerHTML = ''; if (emptyEl) emptyEl.hidden = false; return; }
        buildTags();
        renderQuick();
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
    var pathMatch = location.pathname.match(/^\/column\/([^\/?#]+)$/);
    var slug = pathMatch ? decodeURIComponent(pathMatch[1]) : (new URLSearchParams(location.search).get('slug') || '');
    var box = $('.container', articleEl);

    function fail(msg) {
      box.innerHTML = '<p class="article__error">' + esc(msg) + '</p>' +
        '<p><a class="btn btn--outline btn--sm" href="/">← 칼럼 목록으로</a></p>';
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

        // SEO: 칼럼별 canonical·OG·Article 구조화데이터 갱신
        var canonicalUrl = 'https://taxin4u.com/column/' + encodeURIComponent(slug);
        var descText = p.summary || '세무법인 지율 손창용 세무사의 세무 칼럼.';
        function setAttr(id, attr, val) {
          var el = document.getElementById(id);
          if (el) el.setAttribute(attr, val);
        }
        setAttr('canonicalLink', 'href', canonicalUrl);
        setAttr('ogUrl', 'content', canonicalUrl);
        setAttr('ogTitle', 'content', p.title + ' | 세무법인 지율');
        setAttr('ogDesc', 'content', descText);
        try {
          var ld = {
            '@context': 'https://schema.org',
            '@type': 'Article',
            headline: p.title,
            description: descText,
            author: { '@type': 'Person', name: '손창용', jobTitle: '대표 세무사' },
            publisher: { '@type': 'Organization', name: '세무법인 지율' },
            datePublished: p.date || undefined,
            mainEntityOfPage: canonicalUrl,
            url: canonicalUrl,
            image: 'https://taxin4u.com/assets/images/og.png?v=4'
          };
          var s = document.createElement('script');
          s.type = 'application/ld+json';
          s.textContent = JSON.stringify(ld);
          document.head.appendChild(s);
        } catch (e) { /* 구조화데이터 실패는 본문에 영향 없음 */ }

        var tags = (p.tags || []).map(function (t) {
          return '<a class="post-card__tag" href="/">' + esc(t) + '</a>';
        }).join('');

        // 컨텍스트 노트: '어느 노트에서 왔는지'(?from=). all→없음(← 전체 노트로 충분),
        // 특정 노트 slug→그 노트, 미지정(직접 방문)→대표 노트로 폴백. (서버 SSR과 동일)
        var notes = window.__NOTES || {};
        var fromParam = new URLSearchParams(location.search).get('from');
        var ctx = null;
        if (fromParam === 'all') ctx = null;
        else if (fromParam && notes[fromParam]) ctx = { slug: fromParam, title: notes[fromParam] };
        else ctx = p.primary_hub || null;
        var hubTop = ctx ? ' <a class="article__back-hub" href="/' + encodeURIComponent(ctx.slug) + '">' + esc(ctx.title) + '</a>' : '';
        var moreBtn = ctx ? '<a class="btn btn--outline btn--sm" href="/' + encodeURIComponent(ctx.slug) + '">' + esc(ctx.title) + '에서 더 보기</a> ' : '';

        box.innerHTML =
          '<nav class="article__back"><a href="/">← 전체 세무칼럼 노트</a>' + hubTop +
          '<button class="btn btn--outline btn--sm" type="button" id="printArticleTop">🖨 인쇄 / PDF 저장</button></nav>' +
          '<header class="article__head">' +
          (tags ? '<div class="post-card__tags">' + tags + '</div>' : '') +
          '<h1 class="article__title">' + esc(p.title) + '</h1>' +
          '<div class="article__meta"><time datetime="' + esc(p.date) + '">' + fmtDate(p.date) + '</time>' +
          '<span class="article__author">세무법인 지율 · 손창용 세무사</span>' +
          (SHOW_VIEWS ? '<span class="article__views" id="articleViews" title="조회수">조회 ' + fmtViews(p.views) + '</span>' : '') + '</div>' +
          '</header>' +
          '<div class="article__body prose">' + (p.content_html || '') + '</div>' +
          '<footer class="article__foot">' +
          '<a class="btn btn--outline btn--sm" href="/">← 전체 세무칼럼 노트로 바로 가기</a> ' +
          moreBtn +
          '<button class="btn btn--outline btn--sm" type="button" id="printArticle">🖨 인쇄 / PDF 저장</button> ' +
          '<a class="btn btn--primary btn--sm" href="/contact.html"><span class="only-pc">강의요청 및 상담문의하기</span><span class="only-mo">상담 문의하기</span></a>' +
          '</footer>';
        [document.getElementById('printArticle'), document.getElementById('printArticleTop')]
          .forEach(function (b) { if (b) b.addEventListener('click', function () { window.print(); }); });
        window.scrollTo(0, 0);

        // 함께 읽으면 좋은 칼럼: 태그 공유 많은 순 2편 + 네이버 블로그 링크 (서버 SSR과 동일)
        fetch('/api/posts')
          .then(function (r) { return r.json(); })
          .then(function (d) {
            var all = (d && d.posts) || [];
            var cur = p.tags || [];
            function shared(x) { return (x.tags || []).filter(function (t) { return cur.indexOf(t) >= 0; }).length; }
            var others = all.filter(function (q) { return q.slug !== p.slug; });
            others.sort(function (a, b) {
              var ds = shared(b) - shared(a);
              return ds !== 0 ? ds : String(b.date || '').localeCompare(String(a.date || ''));
            });
            var items = others.slice(0, 2).map(function (r2) {
              var rt = (r2.tags || []).join(' · ');
              return '<li class="related__item"><a class="related__link" href="/column/' + encodeURIComponent(r2.slug) + '">' +
                esc(r2.title) + '</a>' + (rt ? '<span class="related__tags">' + esc(rt) + '</span>' : '') + '</li>';
            }).join('');
            var naver = p.source || 'https://blog.naver.com/taxin4u';
            items += '<li class="related__blog"><a href="' + esc(naver) + '" target="_blank" rel="noopener noreferrer">네이버 블로그에서 더 많은 세무 칼럼 보기 →</a></li>';
            var sec = document.createElement('section');
            sec.className = 'related';
            sec.setAttribute('aria-label', '함께 읽으면 좋은 칼럼');
            sec.innerHTML = '<h2 class="related__title">📚 함께 읽으면 좋은 칼럼</h2><ul class="related__list">' + items + '</ul>';
            var foot = box.querySelector('.article__foot');
            if (foot) box.insertBefore(sec, foot); else box.appendChild(sec);
          })
          .catch(function () {});

        // 조회수 +1 은 기록만 하고, 화면 숫자는 목록과 동일하게(열기 전 값) 유지한다.
        // (증가분은 다음 방문부터 반영 → 목록·상세 표시 불일치 방지)
        fetch('/api/posts/' + encodeURIComponent(slug) + '/view', { method: 'POST' }).catch(function () {});
      })
      .catch(function (err) {
        if (String(err.message) === 'not_found') fail('요청하신 칼럼을 찾을 수 없습니다.');
        else fail('칼럼을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
      });
  }
})();

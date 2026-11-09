/* =========================================================
   세무법인 지율 — 카드뉴스 갤러리 + 라이트박스 뷰어
   cardnews.html(공유페이지 /cardnews/<slug>)과
   index.html(세무칼럼 '카드뉴스' 탭)이 함께 쓴다.
   #cnGrid 가 없는 페이지에서는 아무 일도 하지 않는다.
   ========================================================= */
(function () {
  'use strict';

  var grid = document.getElementById('cnGrid');
  if (!grid) return;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmtDate(d) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || '');
    return m ? m[1] + '.' + m[2] + '.' + m[3] + '.' : '';
  }

  var loading = document.getElementById('cnLoading');
  var empty = document.getElementById('cnEmpty');
  var sets = [];
  // 뷰어를 닫을 때 돌아갈 주소. 페이지마다 다르고(홈 '/?tab=cardnews' vs '/cardnews.html'),
  // 홈에서는 탭을 옮기면 주소가 바뀌므로 열기 직전 주소를 그때그때 기억한다.
  function currentBase() {
    if (/^\/cardnews\//.test(location.pathname)) return '/cardnews.html';
    return location.pathname + location.search;
  }
  var baseUrl = currentBase();

  /* ---------- 목록 ---------- */
  function render(list) {
    grid.innerHTML = list.map(function (s, i) {
      var cover = s.dir + '/' + (s.cards[0] && s.cards[0].file);
      var links = (s.columns || []).map(function (c) {
        return '<a class="cn-card__link" href="/column/' + encodeURIComponent(c.slug) + '">' + esc(c.title) + '</a>';
      }).join('');
      // 자료실에 원문(보도자료·고시 등)이 있으면 바로 내려받을 수 있게 붙인다
      links += (s.files || []).map(function (f) {
        return '<a class="cn-card__link cn-card__link--file" href="/files/' + encodeURIComponent(f.name)
          + '" download>' + esc(f.label || '원문 내려받기') + '</a>';
      }).join('');
      links += '<button class="cn-card__share" type="button" data-share="' + i + '">링크 복사</button>';
      return '' +
        '<article class="cn-card">' +
          '<button class="cn-card__btn" type="button" data-set="' + i + '" aria-label="' + esc(s.title) + ' 카드뉴스 보기">' +
            '<span class="cn-card__thumb">' +
              '<img src="' + esc(cover) + '" alt="' + esc(s.title) + ' 표지" loading="lazy" decoding="async" />' +
              '<span class="cn-card__count">' + s.cards.length + '장</span>' +
            '</span>' +
            '<span class="cn-card__body">' +
              (s.tags && s.tags.length ? '<span class="cn-card__tags">' + esc(s.tags.join(' · ')) + '</span>' : '') +
              '<span class="cn-card__title">' + esc(s.title) + '</span>' +
              (s.subtitle ? '<span class="cn-card__sub">' + esc(s.subtitle) + '</span>' : '') +
              '<span class="cn-card__date">' + esc(fmtDate(s.date)) + '</span>' +
            '</span>' +
          '</button>' +
          (links ? '<div class="cn-card__links">' + links + '</div>' : '') +
        '</article>';
    }).join('');

    grid.querySelectorAll('.cn-card__btn').forEach(function (b) {
      b.addEventListener('click', function () { open(parseInt(b.dataset.set, 10), 0); });
    });
    grid.querySelectorAll('.cn-card__share').forEach(function (b) {
      b.addEventListener('click', function () { share(parseInt(b.dataset.share, 10)); });
    });
  }

  /* ---------- 공유 ---------- */
  var toast = document.getElementById('cnToast');
  var toastTimer = null;
  function showToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('is-on'); }, 2200);
  }
  function setUrl(si) {
    var s = sets[si];
    return location.origin + '/cardnews/' + encodeURIComponent(s.slug);
  }
  // 휴대폰(터치 기기)에서만 기본 공유창을 쓴다. PC 크롬·엣지에도 navigator.share 가
  // 있어서 이걸 기준으로 삼으면 PC 에서 '링크 복사'가 윈도 공유창을 띄워 버린다.
  var isMobile = (window.matchMedia && matchMedia('(pointer: coarse)').matches) ||
    /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
  function share(si) {
    var url = setUrl(si);
    // 주소만 넘긴다 — 제목·설명을 함께 넘기면 카카오톡이 그 글자를 본문에 붙여버려
    // 미리보기 카드 위에 같은 제목이 한 번 더 나온다.
    if (isMobile && navigator.share) {
      navigator.share({ url: url }).catch(function (e) {
        // 사용자가 공유창을 닫은 경우(AbortError)만 조용히 끝내고, 그 밖의 실패는 복사로
        if (!e || e.name !== 'AbortError') copyUrl(url);
      });
      return;
    }
    copyUrl(url);
  }
  function copyUrl(url) {
    if (navigator.clipboard && navigator.clipboard.writeText && window.isSecureContext) {
      navigator.clipboard.writeText(url).then(function () {
        showToast('링크를 복사했습니다');
      }).catch(function () { legacyCopy(url); });
    } else {
      legacyCopy(url);
    }
  }
  function legacyCopy(url) {
    var t = document.createElement('textarea');
    t.value = url;
    t.setAttribute('readonly', '');
    t.style.position = 'fixed';
    t.style.top = '0';
    t.style.left = '0';
    t.style.opacity = '0';
    // 뷰어·body 의 user-select:none 때문에 선택이 막히지 않게
    t.style.userSelect = 'text';
    t.style.webkitUserSelect = 'text';
    document.body.appendChild(t);
    t.focus();
    t.select();
    t.setSelectionRange(0, url.length);
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(t);
    if (ok) showToast('링크를 복사했습니다');
    else window.prompt('아래 주소를 복사하세요', url);
  }

  /* ---------- 뷰어 ---------- */
  var viewer = document.getElementById('cnViewer');
  var img = document.getElementById('cnImg');
  var titleEl = document.getElementById('cnViewerTitle');
  var counter = document.getElementById('cnCounter');
  var dots = document.getElementById('cnDots');
  var prevBtn = document.getElementById('cnPrev');
  var nextBtn = document.getElementById('cnNext');
  var cur = { set: 0, idx: 0 };

  function show() {
    var s = sets[cur.set];
    var card = s.cards[cur.idx];
    img.src = s.dir + '/' + card.file;
    img.alt = card.alt || (s.title + ' ' + (cur.idx + 1) + '번째 카드');
    titleEl.textContent = s.title;
    counter.textContent = (cur.idx + 1) + ' / ' + s.cards.length;
    prevBtn.disabled = cur.idx === 0;
    nextBtn.disabled = cur.idx === s.cards.length - 1;
    dots.innerHTML = s.cards.map(function (c, i) {
      return '<button class="cn-viewer__dot' + (i === cur.idx ? ' is-on' : '') +
             '" type="button" data-i="' + i + '" aria-label="' + (i + 1) + '번째 카드"></button>';
    }).join('');
    dots.querySelectorAll('.cn-viewer__dot').forEach(function (d) {
      d.addEventListener('click', function () { cur.idx = parseInt(d.dataset.i, 10); show(); });
    });
    // 다음 카드 미리 받아두기
    var nxt = s.cards[cur.idx + 1];
    if (nxt) { new Image().src = s.dir + '/' + nxt.file; }
  }

  function open(si, ci) {
    baseUrl = currentBase();
    cur = { set: si, idx: ci };
    viewer.hidden = false;
    document.body.style.overflow = 'hidden';
    document.body.classList.add('cn-open');
    try { history.replaceState(null, '', '/cardnews/' + encodeURIComponent(sets[si].slug)); } catch (e) {}
    show();
  }
  function close() {
    viewer.hidden = true;
    document.body.style.overflow = '';
    document.body.classList.remove('cn-open');
    if (window.getSelection) { window.getSelection().removeAllRanges(); }
    try { history.replaceState(null, '', baseUrl); } catch (e) {}
  }
  function step(d) {
    var s = sets[cur.set];
    var n = cur.idx + d;
    if (n < 0 || n >= s.cards.length) return;
    cur.idx = n;
    show();
  }

  prevBtn.addEventListener('click', function () { step(-1); });
  nextBtn.addEventListener('click', function () { step(1); });
  document.getElementById('cnShare').addEventListener('click', function () { share(cur.set); });
  document.getElementById('cnClose').addEventListener('click', close);
  viewer.addEventListener('click', function (e) { if (e.target === viewer) close(); });
  document.addEventListener('keydown', function (e) {
    if (viewer.hidden) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') step(-1);
    else if (e.key === 'ArrowRight') step(1);
  });
  // 모바일 좌우 스와이프
  var tx = 0, ty = 0;
  viewer.addEventListener('touchstart', function (e) {
    tx = e.changedTouches[0].clientX; ty = e.changedTouches[0].clientY;
  }, { passive: true });
  viewer.addEventListener('touchend', function (e) {
    var dx = e.changedTouches[0].clientX - tx, dy = e.changedTouches[0].clientY - ty;
    if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) step(dx < 0 ? 1 : -1);
  }, { passive: true });

  /* ---------- 데이터 ---------- */
  fetch('/api/cardnews')
    .then(function (r) { return r.json(); })
    .then(function (d) {
      sets = (d && d.cardnews) || [];
      if (loading) loading.hidden = true;
      if (!sets.length) { if (empty) empty.hidden = false; return; }
      render(sets);

      // 공유 주소(/cardnews/<slug>, ?set=, #slug)로 들어오면 그 세트를 바로 연다
      var want = window.__CN_OPEN
        || new URLSearchParams(location.search).get('set')
        || decodeURIComponent((location.hash || '').replace('#', ''));
      if (want) {
        var idx = sets.findIndex(function (s) { return s.slug === want; });
        if (idx >= 0) { open(idx, 0); }
      }
    })
    .catch(function () {
      if (loading) loading.hidden = true;
      if (empty) {
        empty.hidden = false;
        empty.textContent = '카드뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.';
      }
    });
})();

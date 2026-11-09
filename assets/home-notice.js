/* 홈 첫 화면 안내 팝업 — 새 메뉴(카드뉴스 · 연말정산 자가진단) 알림. (2026-11-09)
   - 홈(index.html)에서만 불린다. 「오늘 하루 보지 않기」를 누르면 그날은 다시 안 뜬다(브라우저 저장).
   - END 날짜가 지나면 자동으로 더는 뜨지 않는다. 내용을 바꾸면 KEY 도 바꿔야 이전에 닫은 사람에게 다시 보인다.
   - 검색 크롤러용 내용이 아니므로 HTML 에 넣지 않고 여기서 그린다. */
(function () {
  'use strict';
  var KEY = 'jy_notice_2026_11_newmenu';
  var END = '2027-03-01';            // 연말정산 시즌이 끝나면 자동 종료

  function today() {
    var d = new Date();
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }
  if (today() >= END) return;
  if (/bot|crawl|spider|slurp|headless/i.test(navigator.userAgent)) return;
  try { if (localStorage.getItem(KEY) === today()) return; } catch (e) { /* 저장 불가면 매번 보여도 무방 */ }
  // ?tab= 으로 특정 탭을 열고 들어온 경우(공유 링크 등)는 방해하지 않는다
  if (/[?&]tab=/.test(location.search)) return;

  var css =
    '.jn-back{position:fixed;inset:0;z-index:1000;background:rgba(15,28,46,.55);display:flex;align-items:center;justify-content:center;padding:16px;opacity:0;transition:opacity .2s}' +
    '.jn-back.is-on{opacity:1}' +
    '.jn{position:relative;width:100%;max-width:440px;max-height:calc(100vh - 32px);overflow:auto;background:#fff;border-radius:18px;box-shadow:0 20px 50px rgba(15,28,46,.35);transform:translateY(12px);transition:transform .2s;font-family:var(--font-sans,sans-serif)}' +
    '.jn-back.is-on .jn{transform:none}' +
    '.jn__head{padding:22px 22px 16px;background:linear-gradient(135deg,#1E3A5F,#2A5A9A);color:#fff;border-radius:18px 18px 0 0}' +
    '.jn__eyebrow{display:inline-block;padding:3px 10px;border-radius:999px;background:rgba(255,255,255,.18);font-size:12px;font-weight:800;letter-spacing:.04em}' +
    '.jn__title{margin:10px 0 4px;font-size:21px;font-weight:800;line-height:1.35}' +
    '.jn__lead{margin:0;font-size:14px;color:#C9D9F0;line-height:1.55}' +
    '.jn__x{position:absolute;top:12px;right:12px;width:34px;height:34px;border:0;border-radius:50%;background:rgba(255,255,255,.16);color:#fff;font-size:18px;line-height:1;cursor:pointer}' +
    '.jn__x:hover{background:rgba(255,255,255,.28)}' +
    '.jn__body{padding:16px 18px 6px}' +
    '.jn__item{display:block;padding:14px 16px;margin:0 0 10px;border:1px solid #E2E8F0;border-radius:14px;color:#1F2937;text-decoration:none;transition:border-color .15s,background .15s}' +
    '.jn__item:hover{border-color:#3B82F6;background:#F5F9FF}' +
    '.jn__name{display:flex;align-items:center;gap:6px;font-size:16px;font-weight:800;color:#1E3A5F}' +
    '.jn__new{padding:2px 7px;border-radius:999px;background:#E8F1FF;color:#2563EB;font-size:11px;font-weight:800}' +
    '.jn__new--hot{background:#FFF1E6;color:#C2410C}' +
    '.jn__desc{margin:5px 0 0;font-size:13.5px;color:#5B6B7F;line-height:1.6}' +
    '.jn__go{display:inline-block;margin-top:7px;font-size:13px;font-weight:800;color:#2563EB}' +
    '.jn__foot{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 18px 16px}' +
    '.jn__skip{border:0;background:none;color:#5B6B7F;font:inherit;font-size:13.5px;cursor:pointer;padding:8px 4px;text-decoration:underline}' +
    '.jn__close{border:0;border-radius:10px;background:#1E3A5F;color:#fff;font:inherit;font-size:14.5px;font-weight:800;padding:10px 22px;cursor:pointer}' +
    '.jn__close:hover{background:#152C48}' +
    '@media (max-width:480px){.jn__title{font-size:19px}.jn__head{padding:20px 18px 14px}.jn__body{padding:14px 14px 4px}.jn__foot{padding:6px 14px 14px}}';

  var html =
    '<div class="jn" role="dialog" aria-modal="true" aria-labelledby="jnTitle">' +
      '<div class="jn__head">' +
        '<span class="jn__eyebrow">NEW · 새 메뉴 안내</span>' +
        '<h2 class="jn__title" id="jnTitle">세무칼럼에 새 메뉴가 생겼습니다</h2>' +
        '<p class="jn__lead">인기 칼럼 옆 탭에서 바로 볼 수 있습니다.</p>' +
        '<button class="jn__x" type="button" aria-label="닫기" data-jn="close">✕</button>' +
      '</div>' +
      '<div class="jn__body">' +
        '<a class="jn__item" href="/yearend-check.html">' +
          '<span class="jn__name">연말정산 자가진단 <span class="jn__new jn__new--hot">2026년 귀속</span></span>' +
          '<p class="jn__desc">배우자·부양가족·교육비·월세·주택자금·신용카드 등 <b>14개 공제</b>를 질문에 「예 / 아니오」로 답하면 받을 수 있는지 바로 알려 드립니다. 항목별 링크를 복사해 가족·동료에게 보낼 수도 있습니다.</p>' +
          '<span class="jn__go">자가진단 시작하기 →</span>' +
        '</a>' +
        '<a class="jn__item" href="/cardnews.html">' +
          '<span class="jn__name">카드뉴스 <span class="jn__new">NEW</span></span>' +
          '<p class="jn__desc">세법 개정과 실무 쟁점을 카드 한 장씩으로 정리했습니다. 표지를 누르면 넘겨 보고, 링크 하나로 카카오톡·페이스북에 공유할 수 있습니다.</p>' +
          '<span class="jn__go">카드뉴스 보기 →</span>' +
        '</a>' +
      '</div>' +
      '<div class="jn__foot">' +
        '<button class="jn__skip" type="button" data-jn="today">오늘 하루 보지 않기</button>' +
        '<button class="jn__close" type="button" data-jn="close">닫기</button>' +
      '</div>' +
    '</div>';

  function show() {
    var st = document.createElement('style');
    st.textContent = css;
    document.head.appendChild(st);
    var back = document.createElement('div');
    back.className = 'jn-back';
    back.innerHTML = html;
    document.body.appendChild(back);
    var prevFocus = document.activeElement;
    var prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(function () { back.classList.add('is-on'); });
    var closeBtn = back.querySelector('.jn__close');
    try { closeBtn.focus({ preventScroll: true }); } catch (e) { closeBtn.focus(); }

    function close(skipToday) {
      if (skipToday) { try { localStorage.setItem(KEY, today()); } catch (e) {} }
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
      back.classList.remove('is-on');
      setTimeout(function () { if (back.parentNode) back.parentNode.removeChild(back); }, 200);
      if (prevFocus && prevFocus.focus) { try { prevFocus.focus({ preventScroll: true }); } catch (e) {} }
    }
    function onKey(e) { if (e.key === 'Escape') close(false); }
    document.addEventListener('keydown', onKey);
    back.addEventListener('click', function (e) {
      if (e.target === back) { close(false); return; }
      var b = e.target.closest('[data-jn]');
      if (b) close(b.getAttribute('data-jn') === 'today');
    });
  }

  // 첫 화면이 그려진 뒤 살짝 늦게 띄운다(본문을 먼저 보게)
  function start() { setTimeout(show, 600); }
  if (document.readyState === 'complete') start();
  else window.addEventListener('load', start);
})();

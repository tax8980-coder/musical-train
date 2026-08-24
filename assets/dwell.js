/* =========================================================
   세무법인 지율 — 체류시간 측정 (관리자 통계 '평균 체류시간')
   -------------------------------------------------------
   화면에 실제로 보인 시간만 합산해, 페이지를 떠날 때 한 번만
   POST /api/dwell 로 보낸다. 보내는 값은 경로와 초뿐이며
   개인정보는 수집하지 않는다. 실패는 조용히 무시한다.
   ========================================================= */
(function () {
  'use strict';
  if (window.__jiyulDwell) return;      // 같은 페이지에서 중복 실행 방지
  window.__jiyulDwell = true;

  var visibleMs = 0;
  var since = document.visibilityState === 'visible' ? Date.now() : 0;
  var sent = false;

  function pause() {
    if (since) { visibleMs += Date.now() - since; since = 0; }
  }

  function send() {
    if (sent) return;
    pause();
    var sec = Math.round(visibleMs / 1000);
    if (sec < 1) return;
    sent = true;
    var body = JSON.stringify({ path: location.pathname, sec: sec });
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon('/api/dwell', new Blob([body], { type: 'application/json' }));
      } else {
        var x = new XMLHttpRequest();
        x.open('POST', '/api/dwell', false);
        x.setRequestHeader('Content-Type', 'application/json');
        x.send(body);
      }
    } catch (e) { /* 통계 실패는 무시 */ }
  }

  document.addEventListener('visibilitychange', function () {
    // 모바일은 pagehide 가 오지 않는 경우가 있어 화면이 가려질 때 보낸다
    if (document.visibilityState === 'hidden') send();
    else if (!since) since = Date.now();
  });
  window.addEventListener('pagehide', send);
})();

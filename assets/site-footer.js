/* 공통 사이트 푸터 + 개인정보/이용약관 모달 주입 (intro.html 푸터와 동일)
   사용법: 서브페이지 <body> 끝에서 이 스크립트를 로드하고, 기존 .sub-footer 를
   <footer class="sub-footer" data-site-footer></footer> 로 두면 이 마크업으로 교체됩니다.
   플레이스홀더가 없으면 <main> 뒤(문서 끝)에 삽입합니다. */
(function () {
  'use strict';

  var FOOTER_HTML =
    '<footer class="site-footer" id="location">' +
      '<div class="container">' +
        '<div class="footer__grid">' +
          '<div class="footer__col">' +
            '<p class="footer__logo">' +
              '<span class="footer__logo-brand">세무법인</span>' +
              '<img class="footer__logo-img" src="assets/images/logo-brand.png?v=2" alt="세무법인 지율" onload="this.closest(\'.footer__logo\').classList.add(\'has-img\')" />' +
              '<span class="footer__logo-fallback">' +
                '<span class="footer__logo-mark" aria-hidden="true">' +
                  '<svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">' +
                    '<defs><linearGradient id="ftrLogoG" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2A5A9A"/><stop offset="1" stop-color="#3B82F6"/></linearGradient></defs>' +
                    '<rect width="40" height="40" rx="11" fill="url(#ftrLogoG)"/>' +
                    '<g fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M11 13.5 H29"/><path d="M20 13.5 V19"/><path d="M20 19 L12 27.5"/><path d="M20 19 L28 27.5"/></g>' +
                  '</svg>' +
                '</span>' +
                '<span>세무법인 지율</span>' +
              '</span>' +
            '</p>' +
            '<p class="footer__line">대표 세무사 손창용</p>' +
            '<p class="footer__line">사업자등록번호 [120-85-46063]</p>' +
            '<p class="footer__line footer__line--gap">대표전화 <a href="tel:02-552-6436">[02-552-6436]</a></p>' +
            '<p class="footer__line">이메일 <a href="mailto:asd8980@hanmail.net">[asd8980@hanmail.net]</a></p>' +
            '<p class="footer__line">상담시간 평일 09:30~17:30</p>' +
            '<p class="footer__line footer__line--muted">(점심 11:30~13:00)</p>' +
          '</div>' +
          '<div class="footer__col">' +
            '<h2 class="footer__title">오시는 길</h2>' +
            '<p class="footer__line">[서울시 강남구 선릉로86길 37 덕우빌딩 3층 303호]</p>' +
            '<p class="footer__line">지하철 2호선·분당선 선릉역 1번 출구</p>' +
            '<p class="footer__line">주차 사무실 주차는 어려우며, 롯데록드로즈2차 오피스텔 지하주차장 이용 가능(유료)</p>' +
            '<a class="footer__link-arrow" href="[지도 링크 입력]" target="_blank" rel="noopener noreferrer">지도 보기 <svg class="ico ico--sm" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17 17 7"/><path d="M8 7h9v9"/></svg></a>' +
          '</div>' +
        '</div>' +
        '<div class="footer__bottom">' +
          '<ul class="footer__policy">' +
            '<li><button class="footer__policy-btn" type="button" id="openPrivacy">개인정보 처리방침</button></li>' +
            '<li><button class="footer__policy-btn" type="button" id="openTerms">이용약관</button></li>' +
            '<li><a href="[https://blog.naver.com/taxin4u]" target="_blank" rel="noopener noreferrer">네이버 블로그</a></li>' +
          '</ul>' +
          '<p class="footer__copy">© 2026 세무법인 지율</p>' +
        '</div>' +
        '<p class="footer__disclaimer">본 산출물은 초안이며 실서비스 전환 시 HTTPS 적용, 전송·저장 구간 암호화, 접근권한 통제 및 접속기록 보관, 보유기간 경과 자료 파기, 개인정보 처리방침 게시, 스팸·봇 차단 등 개인정보 보호법상 안전성 확보조치를 별도 검토해야 합니다.</p>' +
      '</div>' +
    '</footer>';

  var PRIVACY_HTML =
    '<div class="modal" id="privacyModal" hidden>' +
      '<div class="modal__overlay" data-modal-close></div>' +
      '<div class="modal__dialog" role="dialog" aria-modal="true" aria-labelledby="privacyModalTitle" tabindex="-1">' +
        '<div class="modal__head">' +
          '<h2 class="modal__title" id="privacyModalTitle">개인정보 처리방침</h2>' +
          '<button class="modal__close" type="button" aria-label="닫기" data-modal-close><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12"/><path d="M18 6 6 18"/></svg></button>' +
        '</div>' +
        '<div class="modal__body legal">' +
          '<p class="legal__lead">세무법인 지율(이하 "법인")은 개인정보 보호법 등 관계 법령을 준수하며, 정보주체의 개인정보를 다음과 같이 처리합니다. 본 처리방침은 초안이며, 시행 전 법인의 실제 처리 현황에 맞추어 확정해야 합니다.</p>' +
          '<h3>1. 수집하는 개인정보 항목</h3>' +
          '<ul><li>홈페이지 상담 신청 시(필수): 성함, 연락처, 이메일, 문의 유형, 문의 내용</li><li>홈페이지 상담 신청 시(선택): 회사명/상호</li><li>자동 수집 항목: 접속 일시, 접속 기록(서버 로그) [자동 수집 항목 확정 필요]</li><li>세무대리 계약 체결 시: [계약 단계 수집항목 입력 — 예: 사업자등록번호, 대표자 성명, 신고 관련 증빙자료]</li></ul>' +
          '<h3>2. 개인정보의 수집·이용 목적</h3>' +
          '<ul><li>상담 신청 접수 확인 및 상담 회신, 상담 내용 검토</li><li>세무대리 계약 체결 여부 협의 및 관련 안내</li><li>민원 처리 및 분쟁 대응을 위한 기록 보존</li></ul>' +
          '<h3>3. 개인정보의 보유·이용 기간</h3>' +
          '<ul><li>상담 신청 정보: 상담 종료일로부터 [보유기간 입력] 경과 후 지체 없이 파기</li><li>세무대리 업무 관련 정보: 관계 법령에서 정한 보존기간(세무 관련 장부·증빙 등) 동안 보관한 후 파기 [해당 법령 및 기간 확정 필요]</li><li>법령에 따른 보존 의무가 있는 경우 해당 기간 동안 분리 보관</li></ul>' +
          '<h3>4. 개인정보의 제3자 제공</h3>' +
          '<p>법인은 정보주체의 개인정보를 제1조·제2조에서 명시한 범위를 넘어 제3자에게 제공하지 않습니다. 다만 다음의 경우는 예외로 합니다.</p>' +
          '<ul><li>정보주체가 사전에 별도로 동의한 경우</li><li>법령에 특별한 규정이 있거나 수사기관이 적법한 절차에 따라 요구한 경우</li><li>세무 신고·불복 등 업무 수행을 위해 국세청·조세심판원 등 관계기관에 제출이 필요한 경우 [제공 항목·근거 확정 필요]</li></ul>' +
          '<h3>5. 개인정보 처리의 위탁</h3>' +
          '<p>법인은 서비스 운영을 위해 아래와 같이 개인정보 처리 업무를 위탁할 수 있으며, 위탁계약 시 개인정보의 안전한 관리에 관한 사항을 문서로 정합니다.</p>' +
          '<ul><li>수탁자: [수탁업체명 입력] / 위탁 업무: [예: 홈페이지 운영·서버 호스팅] / 보유기간: [입력]</li><li>수탁자: [수탁업체명 입력] / 위탁 업무: [예: 세무회계 프로그램 운영] / 보유기간: [입력]</li><li>위탁 사실이 없는 경우 본 항목은 "해당 없음"으로 표기합니다.</li></ul>' +
          '<p>국외 이전이 발생하는 경우 이전받는 자, 이전 국가, 이전 항목·시기·방법을 별도로 고지합니다. [국외 이전 여부 확인 필요]</p>' +
          '<h3>6. 정보주체의 권리와 행사 방법</h3>' +
          '<ul><li>정보주체는 언제든지 개인정보 열람, 정정·삭제, 처리정지, 동의 철회를 요구할 수 있습니다.</li><li>권리 행사는 아래 개인정보 보호책임자에게 서면, 전화, 이메일로 요청할 수 있으며, 법인은 지체 없이 조치합니다.</li><li>법정대리인 또는 위임을 받은 자를 통하여 권리를 행사할 수 있습니다.</li><li>다만 법령에서 보존 의무를 정한 정보는 삭제 요구가 제한될 수 있습니다.</li></ul>' +
          '<h3>7. 개인정보의 파기 절차 및 방법</h3>' +
          '<ul><li>절차: 보유기간이 경과하거나 처리 목적이 달성된 개인정보는 지체 없이(사유 발생일로부터 [파기 기한 입력] 이내) 파기 대상으로 선정하고, 개인정보 보호책임자의 확인을 거쳐 파기합니다.</li><li>방법: 전자적 파일은 복구·재생이 불가능한 방법으로 영구 삭제하며, 종이 문서는 파쇄 또는 소각합니다.</li></ul>' +
          '<h3>8. 개인정보의 안전성 확보 조치</h3>' +
          '<ul><li>개인정보 취급 담당자의 최소화 및 접근권한 관리</li><li>접속기록의 보관 및 위·변조 방지 조치</li><li>전송 구간 암호화(HTTPS) 및 저장 시 암호화 [적용 범위 확정 필요]</li><li>백신 프로그램 설치 및 보안 업데이트, 물리적 보관 장소의 잠금장치 운영</li></ul>' +
          '<h3>9. 개인정보 보호책임자</h3>' +
          '<ul><li>개인정보 보호책임자: [성명 입력] / 직위 [입력]</li><li>연락처: [02-552-6436] / [asd8980@hanmail.net]</li><li>개인정보 침해에 대한 신고·상담이 필요한 경우 개인정보침해신고센터(privacy.kisa.or.kr, 국번없이 118), 개인정보 분쟁조정위원회(kopico.go.kr, 1833-6972)에 문의할 수 있습니다.</li></ul>' +
          '<h3>10. 처리방침의 변경</h3>' +
          '<p>본 처리방침은 [시행일 입력]부터 적용됩니다. 법령·정책 또는 법인의 처리 현황 변경에 따라 내용이 추가·삭제·수정되는 경우 변경 사항을 시행 [사전 공지 일수 입력]일 전부터 홈페이지에 공지합니다.</p>' +
        '</div>' +
      '</div>' +
    '</div>';

  var TERMS_HTML =
    '<div class="modal" id="termsModal" hidden>' +
      '<div class="modal__overlay" data-modal-close></div>' +
      '<div class="modal__dialog" role="dialog" aria-modal="true" aria-labelledby="termsModalTitle" tabindex="-1">' +
        '<div class="modal__head">' +
          '<h2 class="modal__title" id="termsModalTitle">이용약관</h2>' +
          '<button class="modal__close" type="button" aria-label="닫기" data-modal-close><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12"/><path d="M18 6 6 18"/></svg></button>' +
        '</div>' +
        '<div class="modal__body legal">' +
          '<p class="legal__lead">본 약관은 초안이며, 시행 전 법인의 실제 운영 방식에 맞추어 확정해야 합니다.</p>' +
          '<h3>제1조 (목적)</h3><p>본 약관은 세무법인 지율이 운영하는 홈페이지에서 제공하는 정보 및 상담 신청 서비스의 이용 조건과 절차를 정함을 목적으로 합니다.</p>' +
          '<h3>제2조 (정보의 성격)</h3><p>홈페이지에 게시된 내용은 일반적인 정보 제공을 목적으로 하며, 개별 사안에 대한 세무 자문에 해당하지 않습니다. 구체적인 사안은 별도의 검토가 필요합니다.</p>' +
          '<h3>제3조 (상담 신청)</h3><p>상담 신청의 접수는 세무대리 계약의 성립을 의미하지 않으며, 계약은 별도의 약정에 따라 체결됩니다.</p>' +
          '<h3>제4조 (이용자의 의무)</h3><p>이용자는 상담 신청 시 사실에 부합하는 정보를 기재해야 하며, 타인의 개인정보를 무단으로 입력해서는 안 됩니다.</p>' +
          '<h3>제5조 (책임의 제한)</h3><p>법인은 홈페이지 게시 정보의 활용으로 발생한 결과에 대하여 관계 법령이 허용하는 범위에서 책임을 제한합니다. [책임 범위 확정 필요]</p>' +
          '<h3>제6조 (약관의 변경)</h3><p>본 약관은 [시행일 입력]부터 적용되며, 변경 시 홈페이지에 공지합니다.</p>' +
        '</div>' +
      '</div>' +
    '</div>';

  function build(html) {
    var tpl = document.createElement('template');
    tpl.innerHTML = html;
    return tpl.content.firstElementChild;
  }

  function insertFooter() {
    var footerEl = build(FOOTER_HTML);
    var placeholder = document.querySelector('[data-site-footer]');
    if (placeholder && placeholder.parentNode) {
      placeholder.parentNode.replaceChild(footerEl, placeholder);
    } else {
      var main = document.querySelector('main');
      if (main && main.parentNode) {
        main.parentNode.insertBefore(footerEl, main.nextSibling);
      } else {
        document.body.appendChild(footerEl);
      }
    }
    document.body.appendChild(build(PRIVACY_HTML));
    document.body.appendChild(build(TERMS_HTML));
  }

  function wireModals() {
    function openModal(modal) {
      modal.hidden = false;
      document.body.style.overflow = 'hidden';
      var dialog = modal.querySelector('.modal__dialog');
      if (dialog) dialog.focus();
      modal.addEventListener('keydown', onKeydown);
    }
    function closeModal(modal) {
      modal.hidden = true;
      document.body.style.overflow = '';
      modal.removeEventListener('keydown', onKeydown);
    }
    function onKeydown(e) {
      if (e.key === 'Escape') closeModal(e.currentTarget);
    }
    [['#openPrivacy', '#privacyModal'], ['#openTerms', '#termsModal']].forEach(function (pair) {
      var opener = document.querySelector(pair[0]);
      var modal = document.querySelector(pair[1]);
      if (!opener || !modal) return;
      opener.addEventListener('click', function () { openModal(modal); });
      modal.querySelectorAll('[data-modal-close]').forEach(function (el) {
        el.addEventListener('click', function () { closeModal(modal); });
      });
    });
  }

  function init() {
    insertFooter();
    wireModals();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

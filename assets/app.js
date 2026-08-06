/* =========================================================
   세무법인 지율 — 프런트엔드 스크립트
   ========================================================= */
(function () {
  'use strict';

  /* =======================================================
     리드 저장 어댑터
     -------------------------------------------------------
     저장 로직은 이 함수 하나로 분리되어 있습니다.
     다른 시스템(예: 외부 CRM, 구글 시트, 메일 발송 API)으로
     교체할 때 이 함수 내부만 바꾸면 됩니다.

     payload = {
       name, company, phone, email, inquiry_type, message,
       privacy_agreed, agreed_at, source
     }
     반환값 = { receiptNo: 'YY-MMDD-###' }
     실패 시 Error를 throw 합니다.
     ======================================================= */
  var LEAD_API_ENDPOINT = '/api/leads';

  async function submitLead(payload) {
    var res;
    try {
      res = await fetch(LEAD_API_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json;charset=UTF-8' },
        body: JSON.stringify(payload)
      });
    } catch (networkErr) {
      throw new Error('NETWORK_ERROR');
    }

    var data = null;
    try { data = await res.json(); } catch (e) { data = null; }

    if (!res.ok || !data || !data.ok) {
      var reason = (data && (data.error || data.message)) || ('HTTP_' + res.status);
      throw new Error(reason);
    }
    return { receiptNo: data.receipt_no };
  }

  /* =======================================================
     유틸
     ======================================================= */
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  /* =======================================================
     1. 헤더 (스크롤 상태 / 모바일 메뉴)
     ======================================================= */
  var header = $('#siteHeader');
  var gnb = $('#gnb');
  var navToggle = $('#navToggle');
  var navBackdrop = $('#navBackdrop');

  var onScroll = function () {
    if (window.scrollY > 80) header.classList.add('is-scrolled');
    else header.classList.remove('is-scrolled');
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // 햄버거 메뉴는 해당 요소가 있는 페이지(intro 등)에서만 동작
  if (navToggle && gnb && navBackdrop) {
    var setNav = function (open) {
      gnb.classList.toggle('is-open', open);
      header.classList.toggle('is-nav-open', open);
      navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      navToggle.setAttribute('aria-label', open ? '메뉴 닫기' : '메뉴 열기');
      navBackdrop.hidden = !open;
    };
    navToggle.addEventListener('click', function () {
      setNav(navToggle.getAttribute('aria-expanded') !== 'true');
    });
    navBackdrop.addEventListener('click', function () { setNav(false); });
    $$('#gnb a').forEach(function (a) {
      a.addEventListener('click', function () { setNav(false); });
    });
    window.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && navToggle.getAttribute('aria-expanded') === 'true') {
        setNav(false);
        navToggle.focus();
      }
    });
    window.addEventListener('resize', function () {
      if (window.innerWidth > 1023) setNav(false);
    });
  }

  /* =======================================================
     2. 스크롤 진입 fade-up (0.5s, 1회)
     ======================================================= */
  var reveals = $$('.reveal');
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (reduceMotion || !('IntersectionObserver' in window)) {
    reveals.forEach(function (el) { el.classList.add('is-in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-in');
          io.unobserve(entry.target); // 1회만
        }
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.08 });
    reveals.forEach(function (el) { io.observe(el); });
  }

  /* =======================================================
     3. FAQ 아코디언 (한 번에 하나만)
     ======================================================= */
  var triggers = $$('.accordion__trigger');
  triggers.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var isOpen = btn.getAttribute('aria-expanded') === 'true';
      triggers.forEach(function (other) {
        other.setAttribute('aria-expanded', 'false');
        var p = document.getElementById(other.getAttribute('aria-controls'));
        if (p) p.hidden = true;
      });
      if (!isOpen) {
        btn.setAttribute('aria-expanded', 'true');
        var panel = document.getElementById(btn.getAttribute('aria-controls'));
        if (panel) panel.hidden = false;
      }
    });
  });

  /* =======================================================
     4. 서비스 카드 → 문의 유형 자동 세팅
     ======================================================= */
  var typeSelect = $('#inquiryType');
  $$('.service-card__link').forEach(function (link) {
    link.addEventListener('click', function () {
      var value = link.getAttribute('data-inquiry-type');
      if (!value || !typeSelect) return;
      // 완료 카드가 떠 있으면 폼으로 되돌린 뒤 값 세팅
      if (successCard && !successCard.hidden) showForm(false);
      typeSelect.value = value;
      clearFieldError(typeSelect);
      typeSelect.dispatchEvent(new Event('change', { bubbles: true }));
    });
  });

  /* =======================================================
     5. 개인정보 동의 전문보기
     ======================================================= */
  var consentToggle = $('#consentToggle');
  var consentFull = $('#consentFull');
  if (consentToggle && consentFull) {
    consentToggle.addEventListener('click', function () {
      var open = consentToggle.getAttribute('aria-expanded') === 'true';
      consentToggle.setAttribute('aria-expanded', open ? 'false' : 'true');
      consentToggle.textContent = open ? '전문보기' : '접기';
      consentFull.hidden = open;
    });
  }

  /* =======================================================
     6. 문의 폼
     ======================================================= */
  var form = $('#leadForm');
  var successCard = $('#successCard');
  var submitBtn = $('#submitBtn');
  var formAlert = $('#formAlert');
  var messageEl = $('#message');
  var messageCount = $('#messageCount');
  var messageCounter = $('#message-counter');
  var phoneEl = $('#phone');
  var agreeEl = $('#privacyAgreed');
  var receiptNoEl = $('#receiptNo');
  var resetBtn = $('#resetFormBtn');

  var MESSAGE_MIN = 10;
  var MESSAGE_MAX = 1000;

  // 상담 폼이 있는 페이지(contact 등)에서만 폼 로직 실행
  if (form) {

  /* --- 글자수 카운터 --- */
  function updateCounter() {
    var len = messageEl.value.length;
    messageCount.textContent = len.toLocaleString('ko-KR');
    messageCounter.classList.toggle('is-limit', len >= MESSAGE_MAX);
  }
  messageEl.addEventListener('input', function () {
    if (messageEl.value.length > MESSAGE_MAX) {
      messageEl.value = messageEl.value.slice(0, MESSAGE_MAX);
    }
    updateCounter();
    clearFieldError(messageEl);
  });
  updateCounter();

  /* --- 연락처 자동 하이픈 --- */
  function formatPhone(digits) {
    var d = digits.replace(/\D/g, '').slice(0, 11);
    if (d.length < 4) return d;

    // 서울 지역번호 02
    if (d.indexOf('02') === 0) {
      if (d.length <= 5) return d.slice(0, 2) + '-' + d.slice(2);
      if (d.length <= 9) return d.slice(0, 2) + '-' + d.slice(2, 5) + '-' + d.slice(5);
      return d.slice(0, 2) + '-' + d.slice(2, 6) + '-' + d.slice(6, 10);
    }
    // 8자리 대표번호(15xx, 16xx, 18xx)
    if (/^1[568]/.test(d) && d.length <= 8) {
      if (d.length <= 4) return d;
      return d.slice(0, 4) + '-' + d.slice(4, 8);
    }
    // 그 외 3자리 국번
    if (d.length <= 7) return d.slice(0, 3) + '-' + d.slice(3);
    if (d.length <= 10) return d.slice(0, 3) + '-' + d.slice(3, 6) + '-' + d.slice(6);
    return d.slice(0, 3) + '-' + d.slice(3, 7) + '-' + d.slice(7, 11);
  }
  phoneEl.addEventListener('input', function () {
    var caretAtEnd = phoneEl.selectionStart === phoneEl.value.length;
    var formatted = formatPhone(phoneEl.value);
    phoneEl.value = formatted;
    if (caretAtEnd) {
      try { phoneEl.setSelectionRange(formatted.length, formatted.length); } catch (e) {}
    }
    clearFieldError(phoneEl);
  });

  /* --- 오류 표시 --- */
  function fieldOf(input) { return input.closest('.field'); }

  function setFieldError(input, message) {
    var field = fieldOf(input);
    var errorEl = document.getElementById(input.id + '-error');
    if (field) field.classList.add('is-invalid');
    if (errorEl) errorEl.textContent = message;
    input.setAttribute('aria-invalid', 'true');
  }
  function clearFieldError(input) {
    var field = fieldOf(input);
    var errorEl = document.getElementById(input.id + '-error');
    if (field) field.classList.remove('is-invalid');
    if (errorEl) errorEl.textContent = '';
    input.removeAttribute('aria-invalid');
  }
  function clearAllErrors() {
    $$('#leadForm input, #leadForm select, #leadForm textarea').forEach(clearFieldError);
    formAlert.hidden = true;
    formAlert.textContent = '';
  }

  ['name', 'company', 'email'].forEach(function (id) {
    var el = document.getElementById(id);
    el.addEventListener('input', function () { clearFieldError(el); });
  });
  typeSelect.addEventListener('change', function () { clearFieldError(typeSelect); });
  agreeEl.addEventListener('change', function () { clearFieldError(agreeEl); });

  /* --- 검증 --- */
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$/;

  function validate() {
    var errors = [];
    var name = form.name.value.trim();
    var phoneDigits = phoneEl.value.replace(/\D/g, '');
    var email = form.email.value.trim();
    var type = typeSelect.value;
    var message = messageEl.value.trim();

    if (name.length < 2) {
      errors.push([form.name, '성함을 2자 이상 입력해 주세요.']);
    }
    if (!phoneDigits) {
      errors.push([phoneEl, '연락처를 입력해 주세요.']);
    } else if (phoneDigits.length < 9 || phoneDigits.length > 11) {
      errors.push([phoneEl, '연락처는 숫자 9~11자리로 입력해 주세요.']);
    }
    if (!email) {
      errors.push([form.email, '이메일을 입력해 주세요.']);
    } else if (!EMAIL_RE.test(email)) {
      errors.push([form.email, '이메일 형식이 올바르지 않습니다. (예: name@example.com)']);
    }
    if (!type) {
      errors.push([typeSelect, '문의 유형을 선택해 주세요.']);
    }
    if (message.length < MESSAGE_MIN) {
      errors.push([messageEl, '문의 내용을 ' + MESSAGE_MIN + '자 이상 입력해 주세요.']);
    } else if (message.length > MESSAGE_MAX) {
      errors.push([messageEl, '문의 내용은 ' + MESSAGE_MAX.toLocaleString('ko-KR') + '자 이내로 입력해 주세요.']);
    }
    if (!agreeEl.checked) {
      errors.push([agreeEl, '개인정보 수집·이용에 동의해 주셔야 상담 접수가 가능합니다.']);
    }
    return errors;
  }

  /* --- 폼 / 완료 카드 전환 --- */
  function showForm(reset) {
    if (reset) {
      form.reset();
      updateCounter();
      consentToggle.setAttribute('aria-expanded', 'false');
      consentToggle.textContent = '전문보기';
      consentFull.hidden = true;
    }
    clearAllErrors();
    successCard.hidden = true;
    form.hidden = false;
  }
  function showSuccess(receiptNo) {
    receiptNoEl.textContent = receiptNo;
    form.hidden = true;
    successCard.hidden = false;
  }

  resetBtn.addEventListener('click', function () {
    showForm(true);
    form.name.focus();
  });

  /* --- 제출 --- */
  var submitting = false;

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    if (submitting) return;

    clearAllErrors();
    var errors = validate();
    if (errors.length) {
      errors.forEach(function (pair) { setFieldError(pair[0], pair[1]); });
      var firstInput = errors[0][0];
      firstInput.focus({ preventScroll: false });
      return;
    }

    var payload = {
      name: form.name.value.trim(),
      company: form.company.value.trim(),
      phone: phoneEl.value.trim(),
      email: form.email.value.trim(),
      inquiry_type: typeSelect.value,
      message: messageEl.value.trim(),
      privacy_agreed: true,
      agreed_at: new Date().toISOString(),
      source: 'website-landing'
    };

    submitting = true;
    submitBtn.disabled = true;
    var originalLabel = submitBtn.textContent;
    submitBtn.textContent = '접수 중...';

    try {
      var result = await submitLead(payload);
      showSuccess(result.receiptNo);
      successCard.focus && successCard.focus();
    } catch (err) {
      formAlert.textContent = '일시적인 오류가 발생했습니다. 대표전화로 연락 주시기 바랍니다.';
      formAlert.hidden = false;
      if (window.console && console.error) console.error('[submitLead]', err);
    } finally {
      submitting = false;
      submitBtn.disabled = false;
      submitBtn.textContent = originalLabel;
    }
  });

  } // end if (form)

  /* =======================================================
     7. 모달 (개인정보 처리방침 / 이용약관)
     ======================================================= */
  var lastFocused = null;

  function openModal(modal) {
    lastFocused = document.activeElement;
    modal.hidden = false;
    document.body.classList.add('is-locked');
    var dialog = $('.modal__dialog', modal);
    dialog.focus();
    modal.addEventListener('keydown', trapFocus);
  }
  function closeModal(modal) {
    modal.hidden = true;
    document.body.classList.remove('is-locked');
    modal.removeEventListener('keydown', trapFocus);
    if (lastFocused && lastFocused.focus) lastFocused.focus();
  }
  function trapFocus(e) {
    var modal = e.currentTarget;
    if (e.key === 'Escape') { closeModal(modal); return; }
    if (e.key !== 'Tab') return;
    var focusables = $$('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])', modal)
      .filter(function (el) { return el.offsetParent !== null; });
    if (!focusables.length) return;
    var first = focusables[0];
    var last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  var modalMap = [
    ['#openPrivacy', '#privacyModal'],
    ['#openTerms', '#termsModal']
  ];
  modalMap.forEach(function (pair) {
    var opener = $(pair[0]);
    var modal = $(pair[1]);
    if (!opener || !modal) return;
    opener.addEventListener('click', function () { openModal(modal); });
    $$('[data-modal-close]', modal).forEach(function (el) {
      el.addEventListener('click', function () { closeModal(modal); });
    });
  });

  /* =======================================================
     7.5 세무 칼럼 — 홈페이지 최신 3건
     ======================================================= */
  var postGrid = $('#postGrid');
  if (postGrid) {
    var postEmpty = $('#postEmpty');

    var escapeHtml = function (s) {
      return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };
    var formatDate = function (iso) {
      if (!iso) return '';
      var m = String(iso).match(/(\d{4})-(\d{2})-(\d{2})/);
      return m ? (m[1] + '.' + m[2] + '.' + m[3] + '.') : escapeHtml(iso);
    };
    var postCard = function (p) {
      var tags = (p.tags || []).map(function (t) {
        return '<span class="post-card__tag">' + escapeHtml(t) + '</span>';
      }).join('');
      var href = '/column/' + encodeURIComponent(p.slug);
      return '' +
        '<li class="post-card">' +
        '<a class="post-card__link" href="' + href + '">' +
        (tags ? '<div class="post-card__tags">' + tags + '</div>' : '') +
        '<h3 class="post-card__title">' + escapeHtml(p.title) + '</h3>' +
        '<p class="post-card__summary">' + escapeHtml(p.summary) + '</p>' +
        '<div class="post-card__meta">' +
        '<time datetime="' + escapeHtml(p.date) + '">' + formatDate(p.date) + '</time>' +
        '<span class="post-card__go">읽기 <span aria-hidden="true">→</span></span>' +
        '</div></a></li>';
    };

    fetch('/api/posts?limit=3')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var posts = (data && data.posts) || [];
        if (!posts.length) {
          postGrid.hidden = true;
          if (postEmpty) postEmpty.hidden = false;
          return;
        }
        postGrid.innerHTML = posts.map(postCard).join('');
      })
      .catch(function () {
        postGrid.hidden = true;
        if (postEmpty) {
          postEmpty.hidden = false;
          postEmpty.textContent = '칼럼을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.';
        }
      });
  }

  /* =======================================================
     8. 헤더 높이만큼 오프셋된 스무스 스크롤
        (CSS scroll-padding-top 보완 — 구형 브라우저 대응)
     ======================================================= */
  $$('a[href^="#"]').forEach(function (link) {
    link.addEventListener('click', function (e) {
      var id = link.getAttribute('href');
      if (!id || id === '#') return;
      var target = document.querySelector(id);
      if (!target) return;
      e.preventDefault();
      var headerH = header.offsetHeight;
      var top = target.getBoundingClientRect().top + window.scrollY - headerH - 16;
      window.scrollTo({
        top: Math.max(top, 0),
        behavior: reduceMotion ? 'auto' : 'smooth'
      });
      if (history.replaceState) history.replaceState(null, '', id);
    });
  });
})();

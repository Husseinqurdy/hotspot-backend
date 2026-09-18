/*
 * NETSAFI ADS WIDGET v1.1 - inaunga mkono CHAP authentication
 * ============================================================
 * JINSI YA KUTUMIA (kwa kila client, mara MOJA tu):
 *
 * Ndani ya login.html yako (mahali popote unapotaka ad ionekane), ongeza:
 *
 *   <div id="netsafi-ad-slot"></div>
 *   $(if chap-id)
 *   <script>
 *     window.__netsafiChapId = "$(chap-id)";
 *     window.__netsafiChapChallenge = "$(chap-challenge)";
 *   </script>
 *   $(endif)
 *   <script src="https://us.umemeswahili.com/static/ads/ads-widget.js"
 *           data-router-id="5"
 *           data-mac="$(mac-esc)"></script>
 *
 * - data-router-id: ID ya router hii kwenye NetSafi dashboard.
 * - data-mac: ACHA HIVI HIVI ($(mac-esc)) - MikroTik inajaza yenyewe.
 *
 * MUHIMU kwa CHAP (routers nyingi za MikroTik zinatumia hii kwa default):
 * page LAZIMA iwe imeshapakia /md5.js KABLA ya script hii (routers za
 * NetSafi tayari zina hii kwenye login.html - angalia juu ya faili).
 * Widget itatumia hexMD5() iliyopo kwenye page kuhesabu password sahihi.
 *
 * MUHIMU kwa "Sponsored Access": login.html LAZIMA iwe na fomu yenye jina
 * "sendin" (fields za jina "username" na "password" hasa hivyo), mfano:
 *
 *   <form name="sendin" action="$(link-login-only)" method="post">
 *     <input type="hidden" name="username">
 *     <input type="hidden" name="password">
 *     <input type="hidden" name="dst" value="$(link-orig)" />
 *   </form>
 * ============================================================
 */

(function () {
  'use strict';

  var API_BASE = 'https://us.umemeswahili.com/api/ads';

  // ── Pata script tag yenyewe ili kusoma data-attributes zake ──
  var scripts = document.getElementsByTagName('script');
  var thisScript = scripts[scripts.length - 1];
  for (var i = 0; i < scripts.length; i++) {
    if (scripts[i].src && scripts[i].src.indexOf('ads-widget.js') !== -1) {
      thisScript = scripts[i];
      break;
    }
  }

  var ROUTER_ID = thisScript.getAttribute('data-router-id');
  var CLIENT_MAC = thisScript.getAttribute('data-mac') || '';
  // CHAP values - zimewekwa na login.html kabla ya script hii (angalia maelekezo juu)
  var CHAP_ID = window.__netsafiChapId || '';
  var CHAP_CHALLENGE = window.__netsafiChapChallenge || '';

  if (!ROUTER_ID) {
    console.error('[NetSafi Ads] data-router-id haipo kwenye script tag - widget haiwezi kuendelea.');
    return;
  }

  function getSlot() {
    return document.getElementById('netsafi-ad-slot');
  }

  function injectStyles() {
    var style = document.createElement('style');
    style.textContent =
      '.ns-ad-box{font-family:inherit;max-width:420px;margin:12px auto;' +
      'border-radius:10px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.12);' +
      'background:#fff;}' +
      '.ns-ad-media{width:100%;display:block;cursor:pointer;}' +
      '.ns-ad-label{font-size:11px;letter-spacing:.05em;text-transform:uppercase;' +
      'color:#888;padding:6px 10px 0;}' +
      '.ns-ad-title{font-size:14px;font-weight:600;padding:2px 10px 10px;color:#222;}' +
      '.ns-sponsored-box{padding:14px;text-align:center;}' +
      '.ns-sponsored-btn{background:#16a34a;color:#fff;border:none;border-radius:8px;' +
      'padding:10px 18px;font-size:14px;font-weight:600;cursor:pointer;width:100%;}' +
      '.ns-sponsored-btn:disabled{opacity:.6;cursor:not-allowed;}' +
      '.ns-sponsored-msg{font-size:13px;color:#555;margin-top:8px;}';
    document.head.appendChild(style);
  }

  function postJSON(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (r) {
      return r.json().then(function (data) {
        return { ok: r.ok, status: r.status, data: data };
      });
    });
  }

  function recordImpression(adId) {
    postJSON(API_BASE + '/impression/', {
      ad_id: adId,
      router_id: ROUTER_ID,
      client_mac: CLIENT_MAC,
    }).then(function (res) {
      if (res.ok) {
        window._netsafiImpressionId = res.data.id;
      }
    }).catch(function () {});
  }

  function recordClick() {
    if (!window._netsafiImpressionId) return;
    postJSON(API_BASE + '/click/', { impression_id: window._netsafiImpressionId }).catch(function () {});
  }

  function submitHotspotLogin(username, rawPassword) {
    var form = document.forms['sendin'];
    if (!form) {
      console.error(
        '[NetSafi Ads] Fomu "sendin" haikupatikana kwenye login.html - ' +
        'sponsored access haiwezi kuingiza mtumiaji kiotomatiki. Angalia maelekezo juu ya faili hili.'
      );
      return false;
    }

    var finalPassword = rawPassword;

    // Kama router hii inatumia CHAP (kama ilivyo kwa NetSafi routers nyingi),
    // password lazima itumwe ikiwa imefanyiwa hash - si maandishi wazi.
    if (CHAP_ID && CHAP_CHALLENGE) {
      if (typeof window.hexMD5 !== 'function') {
        console.error(
          '[NetSafi Ads] CHAP inahitajika lakini hexMD5() (/md5.js) haipo kwenye page - ' +
          'hakikisha /md5.js imepakiwa KABLA ya ads-widget.js.'
        );
        return false;
      }
      finalPassword = window.hexMD5(CHAP_ID + rawPassword + CHAP_CHALLENGE);
    }

    if (form.elements['username']) form.elements['username'].value = username;
    if (form.elements['password']) form.elements['password'].value = finalPassword;
    form.submit();
    return true;
  }

  function renderBannerOrVideo(ad) {
    var slot = getSlot();
    var box = document.createElement('div');
    box.className = 'ns-ad-box';

    var label = document.createElement('div');
    label.className = 'ns-ad-label';
    label.textContent = 'Imedhaminiwa na ' + (ad.advertiser_name || 'Mtangazaji');
    box.appendChild(label);

    var media;
    if (ad.ad_type === 'video') {
      media = document.createElement('video');
      media.src = ad.media_url;
      media.autoplay = true;
      media.muted = true;
      media.loop = true;
      media.playsInline = true;
    } else {
      media = document.createElement('img');
      media.src = ad.media_url;
      media.alt = ad.title;
    }
    media.className = 'ns-ad-media';

    if (ad.click_url) {
      media.addEventListener('click', function () {
        recordClick();
        window.open(ad.click_url, '_blank');
      });
    }
    box.appendChild(media);

    var title = document.createElement('div');
    title.className = 'ns-ad-title';
    title.textContent = ad.title;
    box.appendChild(title);

    slot.appendChild(box);
    recordImpression(ad.id);
  }

  function renderSponsored(ad) {
    var slot = getSlot();
    var box = document.createElement('div');
    box.className = 'ns-ad-box';

    var label = document.createElement('div');
    label.className = 'ns-ad-label';
    label.textContent = 'Imedhaminiwa na ' + (ad.advertiser_name || 'Mtangazaji');
    box.appendChild(label);

    if (ad.media_url) {
      var img = document.createElement('img');
      img.src = ad.media_url;
      img.alt = ad.title;
      img.className = 'ns-ad-media';
      box.appendChild(img);
    }

    var sBox = document.createElement('div');
    sBox.className = 'ns-sponsored-box';

    var btn = document.createElement('button');
    btn.className = 'ns-sponsored-btn';
    btn.type = 'button';
    btn.textContent = 'Pata dakika ' + ad.sponsored_minutes + ' bure';

    var msg = document.createElement('div');
    msg.className = 'ns-sponsored-msg';

    btn.addEventListener('click', function () {
      if (!CLIENT_MAC) {
        msg.textContent = 'Samahani, imeshindwa kutambua kifaa chako. Jaribu tena.';
        return;
      }
      btn.disabled = true;
      btn.textContent = 'Inasubiri...';

      postJSON(API_BASE + '/grant-sponsored/', {
        ad_id: ad.id,
        router_id: ROUTER_ID,
        client_mac: CLIENT_MAC,
      }).then(function (res) {
        if (res.ok && res.data.allowed) {
          msg.textContent = 'Umepata dakika ' + res.data.minutes + '! Inaingiza...';
          var username = 'SP-' + CLIENT_MAC.replace(/[:\-]/g, '').toUpperCase();
          submitHotspotLogin(username, username);
        } else {
          btn.disabled = false;
          btn.textContent = 'Pata dakika ' + ad.sponsored_minutes + ' bure';
          msg.textContent = (res.data && res.data.message) || 'Imeshindwa. Jaribu tena.';
        }
      }).catch(function () {
        btn.disabled = false;
        btn.textContent = 'Pata dakika ' + ad.sponsored_minutes + ' bure';
        msg.textContent = 'Hitilafu ya muunganiko. Jaribu tena.';
      });
    });

    sBox.appendChild(btn);
    sBox.appendChild(msg);
    box.appendChild(sBox);

    slot.appendChild(box);
    recordImpression(ad.id);
  }

  function init() {
    var slot = getSlot();
    if (!slot) {
      console.warn('[NetSafi Ads] <div id="netsafi-ad-slot"></div> haikupatikana kwenye page.');
      return;
    }

    injectStyles();

    var url = API_BASE + '/active/?router_id=' + encodeURIComponent(ROUTER_ID);
    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data.ad) return; // hakuna ad ya sasa - slot inabaki tupu, hakuna madhara
        var ad = data.ad;
        if (ad.ad_type === 'sponsored_access') {
          renderSponsored(ad);
        } else {
          renderBannerOrVideo(ad);
        }
      })
      .catch(function (e) {
        console.warn('[NetSafi Ads] Imeshindwa kupata ad:', e);
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();


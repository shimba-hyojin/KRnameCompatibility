/* ===================================================================
   Datadog RUM (Real User Monitoring)
   -------------------------------------------------------------------
   バニラ JS で動作。React などのフレームワークは不要。
   Datadog 公式の CDN async スニペット方式を使う。
   スニペットが先にキュー(window.DD_RUM)を作るため、
   SDK の読み込みが遅れても init が失われない。

   取得元 / 취득처:
     Datadog → Digital Experience → Real User Monitoring
       → Applications → name-compat-web

   clientToken は公開前提の値（送信専用・読み取り不可）なので
   HTML/JS に直接書いてよい。API キーとは別物。
   =================================================================== */
(function () {
  'use strict';

  var CONFIG = {
    applicationId: 'ca28452b-d61a-4117-85be-09909c33c1da',
    clientToken: 'pub98ee278e0f6fcc11e4410680f7900907',

    site: 'datadoghq.com',        // EU 組織なら datadoghq.eu
    service: 'name-compat-web',
    env: 'prod',
    version: '1.0.0',

    sessionSampleRate: 100,
    sessionReplaySampleRate: 100,

    // 診断ログをコンソールに出す。動作確認できたら false にしてよい。
    debug: true
  };

  if (!CONFIG.applicationId || !CONFIG.clientToken) {
    if (CONFIG.debug) console.warn('[RUM] applicationId / clientToken が未設定です');
    return;
  }

  var SDK_URL = 'https://www.datadoghq-browser-agent.com/' +
                (CONFIG.site === 'datadoghq.eu' ? 'eu1' : 'us1') +
                '/v5/datadog-rum.js';

  // ---- Datadog 公式 async スニペット --------------------------------
  // window.DD_RUM を先にキューとして定義してから SDK を読み込む。
  // SDK がロードされるとキューに溜まった呼び出しが順に実行される。
  (function (h, o, u, n, d) {
    h = h[d] = h[d] || {
      q: [],
      onReady: function (c) { h.q.push(c); }
    };
    d = o.createElement(u);
    d.async = 1;
    d.src = n;
    n = o.getElementsByTagName(u)[0];
    n.parentNode.insertBefore(d, n);
  })(window, document, 'script', SDK_URL, 'DD_RUM');

  // ---- 初期化 -------------------------------------------------------
  window.DD_RUM.onReady(function () {
    try {
      window.DD_RUM.init({
        applicationId: CONFIG.applicationId,
        clientToken: CONFIG.clientToken,
        site: CONFIG.site,
        service: CONFIG.service,
        env: CONFIG.env,
        version: CONFIG.version,

        sessionSampleRate: CONFIG.sessionSampleRate,
        sessionReplaySampleRate: CONFIG.sessionReplaySampleRate,

        trackResources: true,
        trackUserInteractions: true,
        trackLongTasks: true,

        defaultPrivacyLevel: 'mask-user-input',

        // ---- end-to-end トレースの鍵 ----
        // 同一オリジンへの fetch に x-datadog-* ヘッダーを付与し、
        // ブラウザの操作と Flask の APM トレースを1本に繋げる。
        // localhost:8888（SSH トンネル）でも EC2 の IP でも動くよう
        // オリジン一致で判定する。
        allowedTracingUrls: [
          {
            match: function (url) {
              return url.indexOf(window.location.origin) === 0;
            },
            propagatorTypes: ['datadog', 'tracecontext']
          }
        ],
        traceSampleRate: 100
      });

      if (CONFIG.debug) {
        var ctx = window.DD_RUM.getInternalContext && window.DD_RUM.getInternalContext();
        console.log(
          '[RUM] init 完了',
          {
            application_id: ctx && ctx.application_id,
            session_id: ctx && ctx.session_id,
            env: CONFIG.env,
            service: CONFIG.service
          }
        );
        console.log(
          '[RUM] 送信先を Network タブで確認: browser-intake-' + CONFIG.site
        );
      }
    } catch (e) {
      console.error('[RUM] init に失敗しました:', e);
    }
  });
})();

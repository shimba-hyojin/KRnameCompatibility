/* ===================================================================
   preview.html 専用のモックAPI（デザイン確認用）
   -------------------------------------------------------------------
   バックエンドなしで画面を確認するために fetch() を差し替える。
   画数表とアルゴリズムは backend/hangul.py・compatibility.py と同一。
   本番では使用しない。
   =================================================================== */
(function () {
  'use strict';

  var CHOSUNG = ['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ'];
  var JUNGSUNG = ['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ','ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ'];
  var JONGSUNG = ['','ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ','ㄽ','ㄾ','ㄿ','ㅀ','ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ'];

  var STROKES = {
    'ㄱ':2,'ㄴ':2,'ㄷ':3,'ㄹ':5,'ㅁ':4,'ㅂ':4,'ㅅ':2,'ㅇ':1,'ㅈ':3,'ㅊ':4,'ㅋ':3,'ㅌ':4,'ㅍ':4,'ㅎ':3,
    'ㄲ':4,'ㄸ':6,'ㅃ':8,'ㅆ':4,'ㅉ':6,
    'ㄳ':4,'ㄵ':5,'ㄶ':5,'ㄺ':7,'ㄻ':9,'ㄼ':9,'ㄽ':7,'ㄾ':9,'ㄿ':9,'ㅀ':8,'ㅄ':6,
    'ㅏ':2,'ㅐ':3,'ㅑ':3,'ㅒ':4,'ㅓ':2,'ㅔ':3,'ㅕ':3,'ㅖ':4,'ㅗ':2,'ㅘ':4,'ㅙ':5,'ㅚ':3,'ㅛ':3,
    'ㅜ':2,'ㅝ':4,'ㅞ':5,'ㅟ':3,'ㅠ':3,'ㅡ':1,'ㅢ':2,'ㅣ':1
  };

  var ROLE_LABEL = {
    chosung: '初声(子音)', jungsung: '中声(母音)', jongsung: '終声(パッチム)'
  };

  var TIERS = [
    [90, '運命級', 'これはもう運命。ランチは毎日一緒でいいレベルです。'],
    [80, '大吉',   'かなりの好相性。仕事もプライベートも話が合いそう。'],
    [70, '吉',     'いいバランス。安心して隣の席に座れる相性です。'],
    [60, '中吉',   'そこそこ good。会話のきっかけがあれば一気に伸びます。'],
    [50, '小吉',   '普通が一番。長く付き合えるタイプの相性です。'],
    [40, '末吉',   '少し努力が必要。まずはコーヒーでも一杯どうぞ。'],
    [20, 'がんばれ', '相性は数字だけじゃない…と韓国では言います。'],
    [0,  'ドンマイ', '画数の神様は気分屋なので、明日もう一度どうぞ。']
  ];

  var FORTUNES = [
    '今日は「ありがとう」を3回言うと運が回ってきます。',
    '迷ったら、いつもと違う道で帰ってみましょう。',
    '小さな親切が、大きなラッキーを連れてきます。',
    '今日の幸運アイテムは温かい飲み物です。',
    '返事を後回しにしているメッセージ、今送ると吉。'
  ];

  var OWNER = '심효진';
  var store = {};   // { name: {score, grade_label, lookup_count} }

  function isSyllable(ch) {
    var c = ch.charCodeAt(0);
    return c >= 0xAC00 && c <= 0xD7A3;
  }

  function decompose(name) {
    return name.split('').map(function (ch) {
      var code = ch.charCodeAt(0) - 0xAC00;
      var cho = CHOSUNG[Math.floor(code / 588)];
      var jung = JUNGSUNG[Math.floor((code % 588) / 28)];
      var jongIdx = code % 28;
      var jamos = [
        { char: cho,  role: 'chosung',  role_label: ROLE_LABEL.chosung,  strokes: STROKES[cho] },
        { char: jung, role: 'jungsung', role_label: ROLE_LABEL.jungsung, strokes: STROKES[jung] }
      ];
      if (jongIdx) {
        var jong = JONGSUNG[jongIdx];
        jamos.push({ char: jong, role: 'jongsung', role_label: ROLE_LABEL.jongsung, strokes: STROKES[jong] });
      }
      var total = jamos.reduce(function (sum, j) { return sum + j.strokes; }, 0);
      return { char: ch, jamos: jamos, strokes: total };
    });
  }

  function calculate(partner) {
    var ownerSyl = decompose(OWNER);
    var partnerSyl = decompose(partner);
    var a = ownerSyl.map(function (s) { return s.strokes; });
    var b = partnerSyl.map(function (s) { return s.strokes; });

    var merged = [];
    for (var i = 0; i < Math.max(a.length, b.length); i++) {
      if (i < a.length) merged.push(a[i]);
      if (i < b.length) merged.push(b[i]);
    }

    var rows = [merged.slice()];
    var cur = merged.slice();
    while (cur.length > 2) {
      var next = [];
      for (var k = 0; k < cur.length - 1; k++) next.push((cur[k] + cur[k + 1]) % 10);
      rows.push(next);
      cur = next;
    }

    var score = cur[0] * 10 + cur[1];
    var tier = TIERS.find(function (t) { return score >= t[0]; });

    return {
      owner_name: OWNER,
      partner_name: partner,
      score: score,
      grade: { label: tier[1], comment: tier[2] },
      steps: {
        step1_decompose: { owner: ownerSyl, partner: partnerSyl },
        step2_strokes: { owner: a, partner: b },
        step3_interleaved: merged,
        step4_reduction: rows,
        step5_score: score
      },
      saved: true
    };
  }

  function ranking(limit) {
    var rows = Object.keys(store).map(function (name) {
      return {
        partner_name: name,
        score: store[name].score,
        grade_label: store[name].grade_label,
        lookup_count: store[name].lookup_count
      };
    }).sort(function (x, y) { return y.score - x.score; }).slice(0, limit || 20);

    rows.forEach(function (row, idx) { row.rank = idx + 1; });

    var scores = rows.map(function (r) { return r.score; });
    return {
      owner_name: OWNER,
      ranking: rows,
      stats: {
        total_people: rows.length,
        total_lookups: rows.reduce(function (s, r) { return s + r.lookup_count; }, 0),
        avg_score: rows.length
          ? Math.round(scores.reduce(function (s, v) { return s + v; }, 0) / rows.length * 10) / 10
          : 0
      }
    };
  }

  function respond(body, status) {
    return Promise.resolve({
      ok: (status || 200) < 400,
      status: status || 200,
      json: function () { return Promise.resolve(body); }
    });
  }

  // デモ用の初期データ
  ['타나카', '사토', '스즈키', '와타나베'].forEach(function (n) {
    var r = calculate(n);
    store[n] = { score: r.score, grade_label: r.grade.label, lookup_count: 1 };
  });

  window.fetch = function (url, options) {
    var path = String(url).replace(/^.*\/api/, '');
    var method = (options && options.method) || 'GET';

    // ---- DELETE: 전체 삭제 / 이름 지정 삭제
    if (method === 'DELETE') {
      if (path === '/ranking') {
        var count = Object.keys(store).length;
        store = {};
        return respond({ deleted: count, message: count + '件を削除しました。' });
      }
      var m = path.match(/^\/ranking\/(.+)$/);
      if (m) {
        var target = decodeURIComponent(m[1]);
        if (!store[target]) {
          return respond(
            { deleted: 0, message: '「' + target + '」の記録は見つかりませんでした。' },
            404
          );
        }
        delete store[target];
        return respond({ deleted: 1, message: '「' + target + '」を削除しました。' });
      }
      return respond({ error: 'NOT_FOUND' }, 404);
    }

    if (path.indexOf('/meta') === 0) {
      return respond({ owner_name: OWNER, owner_name_ja: 'シム・ヒョジン', stats: ranking().stats });
    }

    if (path.indexOf('/ranking') === 0) {
      return respond(ranking(20));
    }

    if (path.indexOf('/fortune') === 0) {
      return respond({
        message: FORTUNES[Math.floor(Math.random() * FORTUNES.length)],
        sign: null, item: null, total: null, source: 'fallback'
      });
    }

    if (path.indexOf('/compatibility') === 0) {
      var name = (JSON.parse(options.body).partner_name || '').trim();
      if (!name) return respond({ error: 'EMPTY', message: 'お名前を入力してください。' }, 400);
      if (!name.split('').every(isSyllable)) {
        return respond({ error: 'NOT_HANGUL', message: 'ハングル（한글）で入力してください。例: 야마다' }, 400);
      }
      if (name.length < 2 || name.length > 8) {
        return respond({ error: 'LENGTH', message: '2〜8文字のハングルで入力してください。' }, 400);
      }
      var result = calculate(name);
      var prev = store[name];
      store[name] = {
        score: result.score,
        grade_label: result.grade.label,
        lookup_count: prev ? prev.lookup_count + 1 : 1
      };
      return respond(result);
    }

    return respond({ error: 'NOT_FOUND' }, 404);
  };
})();

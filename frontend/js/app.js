/* ===================================================================
   韓国式 名前相性診断 — frontend logic
   =================================================================== */
(function () {
  'use strict';

  var API = '/api';
  var GAUGE_CIRCUMFERENCE = 2 * Math.PI * 52;   // r=52

  var el = {
    ownerLabel:  document.getElementById('ownerLabel'),
    form:        document.getElementById('diagForm'),
    input:       document.getElementById('partnerName'),
    submitBtn:   document.getElementById('submitBtn'),
    errorBox:    document.getElementById('errorBox'),

    kanaInput:   document.getElementById('kanaInput'),
    kanaResult:  document.getElementById('kanaResult'),
    kanaApply:   document.getElementById('kanaApply'),

    resultCard:  document.getElementById('resultCard'),
    resOwner:    document.getElementById('resOwner'),
    resPartner:  document.getElementById('resPartner'),
    scoreNum:    document.getElementById('scoreNum'),
    gaugeBar:    document.getElementById('gaugeBar'),
    resGrade:    document.getElementById('resGrade'),
    resComment:  document.getElementById('resComment'),
    mechBox:     document.getElementById('mechBox'),

    stepDecompose: document.getElementById('stepDecompose'),
    stepStrokes:   document.getElementById('stepStrokes'),
    stepMerged:    document.getElementById('stepMerged'),
    stepReduce:    document.getElementById('stepReduce'),
    stepFinal:     document.getElementById('stepFinal'),

    rankList:      document.getElementById('rankList'),
    rankStats:     document.getElementById('rankStats'),
    reloadRanking: document.getElementById('reloadRanking'),

    toggleDelete:  document.getElementById('toggleDelete'),
    deletePanel:   document.getElementById('deletePanel'),
    deleteName:    document.getElementById('deleteName'),
    deleteOne:     document.getElementById('deleteOne'),
    deleteAll:     document.getElementById('deleteAll'),
    deleteMsg:     document.getElementById('deleteMsg'),

    cookieBtn:  document.getElementById('cookieBtn'),
    cookieBox:  document.getElementById('cookieBox'),
    cookieMsg:  document.getElementById('cookieMsg'),
    cookieMeta: document.getElementById('cookieMeta')
  };

  var ownerName = '심효진';

  // ----------------------------------------------------------- helpers
  function api(path, options) {
    return fetch(API + path, options).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (body) {
        if (!res.ok) {
          var err = new Error(body.message || 'リクエストに失敗しました。');
          err.code = body.error;
          throw err;
        }
        return body;
      });
    });
  }

  function showError(message) {
    el.errorBox.textContent = message;
    el.errorBox.hidden = false;
  }

  function clearError() {
    el.errorBox.hidden = true;
    el.errorBox.textContent = '';
  }

  function setLoading(button, loading) {
    button.disabled = loading;
    button.classList.toggle('is-loading', loading);
  }

  function numChip(value, variant) {
    var span = document.createElement('span');
    span.className = 'num' + (variant ? ' num--' + variant : '');
    span.textContent = value;
    return span;
  }

  // ----------------------------------------------------------- カタカナ変換
  function updateKanaPreview() {
    var raw = el.kanaInput.value.trim();
    if (!raw) {
      el.kanaResult.textContent = '—';
      el.kanaApply.disabled = true;
      return;
    }
    var converted = window.KanaToHangul.convert(raw);
    if (!converted.hangul) {
      el.kanaResult.textContent = '変換できません';
      el.kanaApply.disabled = true;
      return;
    }
    el.kanaResult.textContent = converted.hangul +
      (converted.unknown.length ? '（' + converted.unknown.join('') + 'は変換不可）' : '');
    el.kanaApply.disabled = false;
    el.kanaApply.dataset.value = converted.hangul;
  }

  el.kanaInput.addEventListener('input', updateKanaPreview);

  el.kanaApply.addEventListener('click', function () {
    var value = el.kanaApply.dataset.value || '';
    if (!value) return;
    el.input.value = value.slice(0, 8);
    clearError();
    el.input.focus();
  });

  // ----------------------------------------------------------- 診断
  el.form.addEventListener('submit', function (event) {
    event.preventDefault();
    clearError();

    var name = el.input.value.trim();
    if (!name) {
      showError('お名前を入力してください。');
      return;
    }

    setLoading(el.submitBtn, true);

    api('/compatibility', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ partner_name: name })
    })
      .then(function (data) {
        renderResult(data);
        return loadRanking();
      })
      .catch(function (err) {
        showError(err.message || '診断に失敗しました。時間をおいてお試しください。');
      })
      .then(function () {
        setLoading(el.submitBtn, false);
      });
  });

  function renderResult(data) {
    el.resultCard.hidden = false;
    el.resOwner.textContent = data.owner_name;
    el.resPartner.textContent = data.partner_name;
    el.resGrade.textContent = data.grade.label;
    el.resComment.textContent = data.grade.comment;

    animateScore(data.score);
    renderSteps(data);

    el.resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function animateScore(score) {
    el.gaugeBar.style.strokeDasharray = GAUGE_CIRCUMFERENCE.toFixed(1);
    el.gaugeBar.style.strokeDashoffset = GAUGE_CIRCUMFERENCE.toFixed(1);
    // reflow を挟んでからアニメーションさせる
    void el.gaugeBar.getBoundingClientRect();
    el.gaugeBar.style.strokeDashoffset =
      (GAUGE_CIRCUMFERENCE * (1 - score / 100)).toFixed(1);

    var start = performance.now();
    var duration = 1000;
    function tick(now) {
      var t = Math.min(1, (now - start) / duration);
      var eased = 1 - Math.pow(1 - t, 3);
      el.scoreNum.textContent = Math.round(score * eased);
      if (t < 1) requestAnimationFrame(tick);
      else el.scoreNum.textContent = score;
    }
    requestAnimationFrame(tick);
  }

  // ----------------------------------------------------------- 計算過程
  function renderSteps(data) {
    var steps = data.steps;

    // ① 자모 분해
    el.stepDecompose.innerHTML = '';
    el.stepDecompose.appendChild(
      jamoRow(data.owner_name, steps.step1_decompose.owner, 'me')
    );
    el.stepDecompose.appendChild(
      jamoRow(data.partner_name, steps.step1_decompose.partner, 'you')
    );

    // ② 획수
    el.stepStrokes.innerHTML = '';
    el.stepStrokes.appendChild(
      strokeLine(data.owner_name, steps.step1_decompose.owner, steps.step2_strokes.owner, 'me')
    );
    el.stepStrokes.appendChild(
      strokeLine(data.partner_name, steps.step1_decompose.partner, steps.step2_strokes.partner, 'you')
    );

    // ③ 교차 배열 — 어느 쪽 숫자인지 색으로 구분
    el.stepMerged.innerHTML = '';
    var ownerLen = steps.step2_strokes.owner.length;
    var partnerLen = steps.step2_strokes.partner.length;
    var order = interleaveOrigins(ownerLen, partnerLen);
    steps.step3_interleaved.forEach(function (value, idx) {
      el.stepMerged.appendChild(numChip(value, order[idx]));
    });

    // ④ 인접합 피라미드
    el.stepReduce.innerHTML = '';
    steps.step4_reduction.forEach(function (row, rowIdx) {
      var line = document.createElement('div');
      line.className = 'numrow';
      var isLast = rowIdx === steps.step4_reduction.length - 1;
      row.forEach(function (value, colIdx) {
        var variant = null;
        if (isLast) variant = 'last';
        else if (rowIdx === 0) variant = order[colIdx];
        line.appendChild(numChip(value, variant));
      });
      el.stepReduce.appendChild(line);
    });

    // ⑤ 최종
    var last = steps.step4_reduction[steps.step4_reduction.length - 1];
    el.stepFinal.textContent =
      last[0] + ' と ' + last[1] + ' → ' + data.score + '%';
  }

  function interleaveOrigins(ownerLen, partnerLen) {
    var origins = [];
    for (var i = 0; i < Math.max(ownerLen, partnerLen); i++) {
      if (i < ownerLen) origins.push('me');
      if (i < partnerLen) origins.push('you');
    }
    return origins;
  }

  function jamoRow(name, syllables, variant) {
    var row = document.createElement('div');
    row.className = 'jamo-row';

    var who = document.createElement('span');
    who.className = 'jamo-row__who';
    who.textContent = name;
    row.appendChild(who);

    syllables.forEach(function (syl) {
      var box = document.createElement('span');
      box.className = 'jamo-syl';

      var char = document.createElement('span');
      char.className = 'jamo-syl__char';
      char.textContent = syl.char;
      box.appendChild(char);

      var eq = document.createElement('span');
      eq.className = 'jamo-syl__eq';
      eq.textContent = '=';
      box.appendChild(eq);

      syl.jamos.forEach(function (jamo, idx) {
        var chip = document.createElement('span');
        chip.className = 'jamo-chip';
        chip.innerHTML = (idx > 0 ? '+ ' : '') +
          '<b>' + jamo.char + '</b>' + jamo.strokes;
        chip.title = jamo.role_label + ' / ' + jamo.strokes + '画';
        box.appendChild(chip);
      });

      var sum = document.createElement('span');
      sum.className = 'jamo-syl__sum';
      sum.textContent = syl.strokes + '画';
      box.appendChild(sum);

      row.appendChild(box);
    });

    return row;
  }

  function strokeLine(name, syllables, strokes, variant) {
    var line = document.createElement('div');
    line.className = 'stroke-line';

    var who = document.createElement('span');
    who.className = 'stroke-line__who';
    who.textContent = name;
    line.appendChild(who);

    strokes.forEach(function (value, idx) {
      var wrapper = document.createElement('span');
      wrapper.style.display = 'inline-flex';
      wrapper.style.alignItems = 'center';
      wrapper.style.gap = '4px';
      wrapper.style.marginRight = '8px';

      var label = document.createElement('span');
      label.style.fontWeight = '700';
      label.textContent = syllables[idx] ? syllables[idx].char : '';
      wrapper.appendChild(label);
      wrapper.appendChild(numChip(value, variant));
      line.appendChild(wrapper);
    });

    return line;
  }

  // ----------------------------------------------------------- ランキング
  function loadRanking() {
    return api('/ranking?limit=20')
      .then(function (data) {
        renderRanking(data);
      })
      .catch(function () {
        el.rankList.innerHTML =
          '<li class="rank__empty">ランキングを取得できませんでした。</li>';
      });
  }

  var MEDALS = ['🥇', '🥈', '🥉'];

  function renderRanking(data) {
    var rows = data.ranking || [];
    el.rankList.innerHTML = '';

    if (data.stats) {
      el.rankStats.textContent =
        '参加者 ' + data.stats.total_people + '人 / 診断回数 ' +
        data.stats.total_lookups + '回 / 平均相性 ' + data.stats.avg_score + '%';
    }

    if (!rows.length) {
      el.rankList.innerHTML =
        '<li class="rank__empty">まだ誰も診断していません。</li>';
      return;
    }

    rows.forEach(function (row) {
      var li = document.createElement('li');
      li.className = 'rank__item' + (row.rank <= 3 ? ' rank__item--top' + row.rank : '');

      var no = document.createElement('span');
      no.className = 'rank__no';
      no.textContent = row.rank <= 3 ? MEDALS[row.rank - 1] : row.rank;
      li.appendChild(no);

      var nameBox = document.createElement('span');
      nameBox.className = 'rank__name';
      nameBox.textContent = row.partner_name;
      var grade = document.createElement('span');
      grade.className = 'rank__grade';
      grade.textContent = ' ' + row.grade_label;
      nameBox.appendChild(grade);
      li.appendChild(nameBox);

      var score = document.createElement('span');
      score.className = 'rank__score';
      score.textContent = row.score + '%';
      li.appendChild(score);

      el.rankList.appendChild(li);
    });
  }

  el.reloadRanking.addEventListener('click', function () {
    setLoading(el.reloadRanking, true);
    loadRanking().then(function () { setLoading(el.reloadRanking, false); });
  });

  // ----------------------------------------------------------- 削除
  el.toggleDelete.addEventListener('click', function () {
    el.deletePanel.hidden = !el.deletePanel.hidden;
    el.deleteMsg.hidden = true;
    if (!el.deletePanel.hidden) el.deleteName.focus();
  });

  function showDeleteMsg(text, ok) {
    el.deleteMsg.textContent = text;
    el.deleteMsg.className = 'danger__msg ' + (ok ? 'danger__msg--ok' : 'danger__msg--err');
    el.deleteMsg.hidden = false;
  }

  el.deleteOne.addEventListener('click', function () {
    var name = el.deleteName.value.trim();
    if (!name) {
      showDeleteMsg('お名前を入力してください。', false);
      return;
    }
    if (!window.confirm('「' + name + '」の記録を削除します。よろしいですか？')) return;

    setLoading(el.deleteOne, true);
    api('/ranking/' + encodeURIComponent(name), { method: 'DELETE' })
      .then(function (data) {
        showDeleteMsg(data.message, true);
        el.deleteName.value = '';
        return loadRanking();
      })
      .catch(function (err) {
        showDeleteMsg(err.message || '削除に失敗しました。', false);
      })
      .then(function () { setLoading(el.deleteOne, false); });
  });

  el.deleteAll.addEventListener('click', function () {
    if (!window.confirm('ランキングを全部削除します。元に戻せません。よろしいですか？')) return;

    setLoading(el.deleteAll, true);
    api('/ranking', { method: 'DELETE' })
      .then(function (data) {
        showDeleteMsg(data.message, true);
        return loadRanking();
      })
      .catch(function (err) {
        showDeleteMsg(err.message || '削除に失敗しました。', false);
      })
      .then(function () { setLoading(el.deleteAll, false); });
  });

  // ----------------------------------------------------------- フォーチュンクッキー
  el.cookieBtn.addEventListener('click', function () {
    setLoading(el.cookieBtn, true);
    api('/fortune')
      .then(function (data) {
        el.cookieBox.hidden = false;
        el.cookieMsg.textContent = data.message;
        var meta = [];
        if (data.sign) meta.push(data.sign);
        if (data.item) meta.push('ラッキーアイテム: ' + data.item);
        meta.push(data.source === 'api' ? '外部API より' : 'オフラインメッセージ');
        el.cookieMeta.textContent = meta.join(' ・ ');
      })
      .catch(function () {
        el.cookieBox.hidden = false;
        el.cookieMsg.textContent = 'クッキーが割れませんでした…もう一度どうぞ。';
        el.cookieMeta.textContent = '';
      })
      .then(function () {
        setLoading(el.cookieBtn, false);
      });
  });

  // ----------------------------------------------------------- 初期化
  api('/meta')
    .then(function (data) {
      ownerName = data.owner_name || ownerName;
      el.ownerLabel.textContent = data.owner_name_ja || ownerName;
      el.resOwner.textContent = ownerName;
    })
    .catch(function () { /* メタ取得失敗は致命的ではない */ });

  loadRanking();
})();

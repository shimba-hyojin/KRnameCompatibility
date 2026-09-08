/* ===================================================================
   カタカナ / ひらがな → ハングル 変換
   -------------------------------------------------------------------
   日本人ユーザーは韓国語キーボードを持っていないので、
   カタカナ入力からハングルを作れる補助機能を提供する。

   韓国の外来語表記法（일본어의 가나와 한글 대조표）に近い規則:
     * カ行・タ行 は語頭では平音（가/다）、語中では激音（카/타）
     * 「ツ」は常に「쓰」
     * 長音「ー」は表記しない
     * 撥音「ン」は パッチム ㄴ
     * 促音「ッ」は パッチム ㅅ
   =================================================================== */
(function (global) {
  'use strict';

  var JONG_N = 4;   // ㄴ
  var JONG_S = 19;  // ㅅ

  // 語中（デフォルト）の対応表
  var MAP = {
    'ア': '아', 'イ': '이', 'ウ': '우', 'エ': '에', 'オ': '오',
    'カ': '카', 'キ': '키', 'ク': '쿠', 'ケ': '케', 'コ': '코',
    'サ': '사', 'シ': '시', 'ス': '스', 'セ': '세', 'ソ': '소',
    'タ': '타', 'チ': '치', 'ツ': '쓰', 'テ': '테', 'ト': '토',
    'ナ': '나', 'ニ': '니', 'ヌ': '누', 'ネ': '네', 'ノ': '노',
    'ハ': '하', 'ヒ': '히', 'フ': '후', 'ヘ': '헤', 'ホ': '호',
    'マ': '마', 'ミ': '미', 'ム': '무', 'メ': '메', 'モ': '모',
    'ヤ': '야', 'ユ': '유', 'ヨ': '요',
    'ラ': '라', 'リ': '리', 'ル': '루', 'レ': '레', 'ロ': '로',
    'ワ': '와', 'ヲ': '오', 'ヰ': '이', 'ヱ': '에',
    'ガ': '가', 'ギ': '기', 'グ': '구', 'ゲ': '게', 'ゴ': '고',
    'ザ': '자', 'ジ': '지', 'ズ': '즈', 'ゼ': '제', 'ゾ': '조',
    'ダ': '다', 'ヂ': '지', 'ヅ': '즈', 'デ': '데', 'ド': '도',
    'バ': '바', 'ビ': '비', 'ブ': '부', 'ベ': '베', 'ボ': '보',
    'パ': '파', 'ピ': '피', 'プ': '푸', 'ペ': '페', 'ポ': '포',
    'ヴ': '부',
    // 拗音
    'キャ': '캬', 'キュ': '큐', 'キョ': '쿄', 'キェ': '켸',
    'ギャ': '갸', 'ギュ': '규', 'ギョ': '교',
    'シャ': '샤', 'シュ': '슈', 'ショ': '쇼', 'シェ': '셰',
    'ジャ': '자', 'ジュ': '주', 'ジョ': '조', 'ジェ': '제',
    'チャ': '차', 'チュ': '추', 'チョ': '초', 'チェ': '체',
    'ニャ': '냐', 'ニュ': '뉴', 'ニョ': '뇨',
    'ヒャ': '햐', 'ヒュ': '휴', 'ヒョ': '효',
    'ビャ': '뱌', 'ビュ': '뷰', 'ビョ': '뵤',
    'ピャ': '퍄', 'ピュ': '퓨', 'ピョ': '표',
    'ミャ': '먀', 'ミュ': '뮤', 'ミョ': '묘',
    'リャ': '랴', 'リュ': '류', 'リョ': '료',
    'ファ': '파', 'フィ': '피', 'フェ': '페', 'フォ': '포', 'フュ': '휴',
    'ティ': '티', 'トゥ': '투', 'ディ': '디', 'ドゥ': '두',
    'ウィ': '위', 'ウェ': '웨', 'ウォ': '워',
    'ヴァ': '바', 'ヴィ': '비', 'ヴェ': '베', 'ヴォ': '보',
    'ツァ': '차', 'ツィ': '치', 'ツェ': '체', 'ツォ': '초'
  };

  // 語頭のみ平音になるもの
  var MAP_INITIAL = {
    'カ': '가', 'キ': '기', 'ク': '구', 'ケ': '게', 'コ': '고',
    'タ': '다', 'チ': '지', 'テ': '데', 'ト': '도'
  };
  MAP_INITIAL['キャ'] = '갸';
  MAP_INITIAL['キュ'] = '규';
  MAP_INITIAL['キョ'] = '교';
  MAP_INITIAL['チャ'] = '자';
  MAP_INITIAL['チュ'] = '주';
  MAP_INITIAL['チョ'] = '조';
  MAP_INITIAL['チェ'] = '제';
  MAP_INITIAL['ティ'] = '디';
  MAP_INITIAL['トゥ'] = '두';

  var SMALL = 'ャュョァィゥェォ';

  /** ひらがな → カタカナ、全角統一、不要文字の除去 */
  function normalize(text) {
    var out = '';
    for (var i = 0; i < text.length; i++) {
      var code = text.charCodeAt(i);
      // ひらがな(ぁ-ゖ) → カタカナ
      if (code >= 0x3041 && code <= 0x3096) {
        out += String.fromCharCode(code + 0x60);
      } else {
        out += text[i];
      }
    }
    // 半角スペース/中黒/長音記号の異体を統一
    return out.replace(/[・･\s]+/g, '').replace(/[〜~－―—–ｰ]/g, 'ー');
  }

  /** ハングル音節にパッチムを付ける */
  function addJongsung(syllable, jongIdx) {
    if (!syllable) return syllable;
    var code = syllable.charCodeAt(syllable.length - 1) - 0xAC00;
    if (code < 0 || code > 11171) return syllable;
    var jong = code % 28;
    if (jong !== 0) return syllable;               // 既にパッチムあり
    var cho = Math.floor(code / 588);
    var jung = Math.floor((code % 588) / 28);
    var composed = String.fromCharCode(0xAC00 + (cho * 21 + jung) * 28 + jongIdx);
    return syllable.slice(0, -1) + composed;
  }

  /**
   * 直前のハングル音節の母音が o / u / その他 のどれかを判定する。
   * 長音（おう・おお・うう）を省略するために使う。
   */
  function lastVowelClass(text) {
    if (!text) return null;
    var code = text.charCodeAt(text.length - 1) - 0xAC00;
    if (code < 0 || code > 11171) return null;
    if (code % 28 !== 0) return null;                 // パッチムがあれば長音扱いしない
    var jung = Math.floor((code % 588) / 28);
    if (jung === 8 || jung === 12) return 'o';        // ㅗ, ㅛ
    if (jung === 13 || jung === 17) return 'u';       // ㅜ, ㅠ
    return 'other';
  }

  /**
   * カタカナ文字列をハングルに変換する。
   * @returns {{hangul: string, unknown: string[]}}
   */
  function kanaToHangul(raw) {
    var text = normalize(String(raw || ''));
    var result = '';
    var unknown = [];
    var isFirst = true;
    var i = 0;

    while (i < text.length) {
      var ch = text[i];

      // 長音は表記しない
      if (ch === 'ー') { i++; continue; }

      // 促音 ッ -> 直前の音節に ㅅ
      if (ch === 'ッ' || ch === 'ｯ') {
        result = addJongsung(result, JONG_S);
        i++;
        continue;
      }

      // 撥音 ン -> 直前の音節に ㄴ
      if (ch === 'ン') {
        if (result) {
          result = addJongsung(result, JONG_N);
        } else {
          result += '은';
        }
        i++;
        continue;
      }

      // 拗音（2文字）を優先して照合
      var two = text.substr(i, 2);
      if (two.length === 2 && SMALL.indexOf(two[1]) >= 0) {
        var mappedTwo = (isFirst && MAP_INITIAL[two]) || MAP[two];
        if (mappedTwo) {
          result += mappedTwo;
          isFirst = false;
          i += 2;
          continue;
        }
      }

      // 長音の省略: おう / おお / うう は伸ばす音なので書かない
      //   さとう -> 사토,  こんどう -> 곤도,  ゆうこ -> 유코
      var lastV = lastVowelClass(result);
      if ((ch === 'ウ' && (lastV === 'o' || lastV === 'u')) ||
          (ch === 'オ' && lastV === 'o')) {
        i++;
        continue;
      }

      // 単独カナ
      var mapped = (isFirst && MAP_INITIAL[ch]) || MAP[ch];
      if (mapped) {
        result += mapped;
        isFirst = false;
        i += 1;
        continue;
      }

      // 変換できない文字（漢字・アルファベットなど）
      unknown.push(ch);
      i += 1;
    }

    return { hangul: result, unknown: unknown };
  }

  global.KanaToHangul = { convert: kanaToHangul, normalize: normalize };
})(typeof window !== 'undefined' ? window : globalThis);

/* Node からもテストできるように */
if (typeof module !== 'undefined' && module.exports) {
  module.exports = (typeof window !== 'undefined' ? window : globalThis).KanaToHangul;
}

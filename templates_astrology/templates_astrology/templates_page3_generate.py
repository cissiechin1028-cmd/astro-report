# -*- coding: utf-8 -*-
"""
Page3｜総合生成ロジック

・太陽テンプレート（価値観・方向性）
・月テンプレート（感情のクセ）
・上昇テンプレート（雰囲気・第一印象のタイプ）
・相性スコア（太陽／月／上昇の四元素バランス）
・相性診断（一行まとめ）

をまとめて生成するためのヘルパー関数を定義。
"""

from templates_astrology.templates_page3_a import (
    # ここはあなたの templates_page3_a.py に合わせて調整
    # build_page3_a は、これまで作った「A案（太陽12・月12・上昇4の自動組み合わせ）」関数を想定
    build_page3_a,
)
from templates_astrology.templates_page3_score import (
    get_page3_score_block,
)


def generate_page3(
    your_name: str,
    partner_name: str,
    your_sun: str,
    your_moon: str,
    your_asc: str,
    partner_sun: str,
    partner_moon: str,
    partner_asc: str,
) -> dict:
    """
    Page3 一式をまとめて生成するメイン関数。

    Parameters
    ----------
    your_name : str
        あなたの名前（{your_name} 置換用）
    partner_name : str
        お相手の名前（{partner_name} 置換用）
    your_sun : str
        あなたの太陽星座（例："牡羊座"）
    your_moon : str
        あなたの月星座
    your_asc : str
        あなたの上昇星座
    partner_sun : str
        お相手の太陽星座
    partner_moon : str
        お相手の月星座
    partner_asc : str
        お相手の上昇星座

    Returns
    -------
    dict
        {
          "texts": {...},   # templates_page3_a.build_page3_a の戻り値そのまま
          "scores": {
             "score_total": int,
             "score_communication": int,
             "score_emotion": int,
             "score_values": int,
          },
          "relation_type": "A" | "B" | "C" | "D",
          "relation_sentence": str,   # 一行の相性まとめ
        }
    """

    # 1) 太陽・月・上昇の四元素から相性スコアを計算
    score_block = get_page3_score_block(
        your_sun,
        your_moon,
        your_asc,
        partner_sun,
        partner_moon,
        partner_asc,
    )
    # score_block = {
    #   "scores": {...},
    #   "type": "A/B/C/D",
    #   "one_line": "相性の一行まとめ",
    # }

    relation_type = score_block["type"]           # "A" / "B" / "C" / "D"
    relation_sentence = score_block["one_line"]   # 一行の相性診断
    scores = score_block["scores"]                # 各スコア dict

    # 2) A案のテンプレートロジックで、太陽＋月＋上昇テキストをまとめて生成
    #    ※ ここでは「上昇4タイプ」の選択キーとして relation_type をそのまま使う想定
    #       → Asc テンプレは "A" / "B" / "C" / "D" の4種類
    page3_texts = build_page3_a(
        your_name=your_name,
        partner_name=partner_name,
        sun_sign=your_sun,
        moon_sign=your_moon,
        asc_pattern=relation_type,
    )

    # 3) すべてまとめて返す
    return {
        "texts": page3_texts,
        "scores": scores,
        "relation_type": relation_type,
        "relation_sentence": relation_sentence,
    }

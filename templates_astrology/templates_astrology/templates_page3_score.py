# -*- coding: utf-8 -*-
"""
Page3｜相性スコア + 相性診断（結論文）
"""

# ---------------------------------------------------------
# 1. 星座 → 四元素（火・土・風・水）
# ---------------------------------------------------------

ELEMENT_TABLE = {
    # 火
    "牡羊座": "火", "獅子座": "火", "射手座": "火",
    # 土
    "牡牛座": "土", "乙女座": "土", "山羊座": "土",
    # 風
    "双子座": "風", "天秤座": "風", "水瓶座": "風",
    # 水
    "蟹座": "水", "蠍座": "水", "魚座": "水",
}

# ---------------------------------------------------------
# 2. 四元素之间的相性表（得点）
# ---------------------------------------------------------
# 100% 安定：風×火 / 水×土 / 同元素
# 70% 中程度：火×土 / 風×水（やや調整必要）
# 50% やや難：火×水 / 土×風（噛み合いにくい）

ELEMENT_SCORE = {
    ("火", "火"): 90, ("土", "土"): 90, ("風", "風"): 90, ("水", "水"): 90,

    ("火", "風"): 85, ("風", "火"): 85,
    ("土", "水"): 85, ("水", "土"): 85,

    ("火", "土"): 70, ("土", "火"): 70,
    ("風", "水"): 70, ("水", "風"): 70,

    ("火", "水"): 55, ("水", "火"): 55,
    ("土", "風"): 55, ("風", "土"): 55,
}

# ---------------------------------------------------------
# 3. 得点計算
# ---------------------------------------------------------

def compute_pair_score(sun1, moon1, asc1, sun2, moon2, asc2):
    """
    return dict:
    {
        "score_total": int,
        "score_communication": int,
        "score_emotion": int,
        "score_values": int,
    }
    """

    def elem(zodiac):
        return ELEMENT_TABLE.get(zodiac, None)

    # 各要素
    s1, m1, a1 = elem(sun1), elem(moon1), elem(asc1)
    s2, m2, a2 = elem(sun2), elem(moon2), elem(asc2)

    # 基于元素评分
    def pair(e1, e2):
        if e1 is None or e2 is None:
            return 70  # fallback
        return ELEMENT_SCORE.get((e1, e2), 70)

    # 三段评分
    values_score = pair(s1, s2)          # 価値観・行動傾向（太陽）
    emotion_score = pair(m1, m2)         # 心の相性（月）
    communication_score = pair(a1, a2)   # 雰囲気・テンポ（上昇）

    # 総合
    total = int((values_score + emotion_score + communication_score) / 3)

    return {
        "score_total": total,
        "score_communication": communication_score,
        "score_emotion": emotion_score,
        "score_values": values_score,
    }

# ---------------------------------------------------------
# 4. 結論タイプ判定（A/B/C/D）
# ---------------------------------------------------------

def classify_relation_type(values_score, emotion_score, communication_score):
    """
    A：自然体・調和（総合が高く安定）
    B：テンポ差・勢い（火・風が強く、コミュニケーション高・感情低）
    C：感情ケア型（月スコアが主役）
    D：違い×補完型（凸凹・スコア差が大きい）
    """

    # A：全体80以上 → 安定
    if values_score >= 80 and emotion_score >= 80 and communication_score >= 80:
        return "A"

    # B：火風強 → コミュニケーション高め / 感情低め
    if communication_score >= 80 and emotion_score <= 70:
        return "B"

    # C：水要素強 → 感情領域が主役
    if emotion_score >= 80 and values_score < 80:
        return "C"

    # D：スコア差が大きい（20点以上）
    smax = max(values_score, emotion_score, communication_score)
    smin = min(values_score, emotion_score, communication_score)
    if smax - smin >= 20:
        return "D"

    # fallback
    if (values_score + emotion_score + communication_score) / 3 >= 75:
        return "A"
    return "D"

# ---------------------------------------------------------
# 5. パターン別の結論文（1行）
# ---------------------------------------------------------

RELATION_ONE_LINE = {
    "A": "自然体で歩幅がそろいやすい、穏やかな相性です。",
    "B": "テンポに勢いがあり、動きの中で深まりやすい相性です。",
    "C": "感情のケアを通して、ゆっくり信頼が育つ相性です。",
    "D": "違いが補い合い、バランスが形になっていく相性です。",
}

def get_relation_conclusion(pattern):
    return RELATION_ONE_LINE.get(pattern, RELATION_ONE_LINE["A"])

# ---------------------------------------------------------
# 6. 外部呼び出し用メイン関数
# ---------------------------------------------------------

def get_page3_score_block(sun1, moon1, asc1, sun2, moon2, asc2):
    """
    return:
    {
        "scores": { ... },
        "type": "A/B/C/D",
        "one_line": "...",
    }
    """

    scores = compute_pair_score(sun1, moon1, asc1, sun2, moon2, asc2)

    ptype = classify_relation_type(
        scores["score_values"],
        scores["score_emotion"],
        scores["score_communication"],
    )

    one_line = get_relation_conclusion(ptype)

    return {
        "scores": scores,
        "type": ptype,
        "one_line": one_line,
    }

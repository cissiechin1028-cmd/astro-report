# -*- coding: utf-8 -*-
"""
Page3 Aプラン用：太陽・月・ASC テキスト生成

generate_page3(...) ->
    {
        "sun_block":  "...",
        "moon_block": "...",
        "asc_block":  "...",
    }

今はまず「ちゃんと動く」ことを優先して、
太陽12 / 月12 / ASC4 それぞれにエントリを用意しつつ、
文章内容はタイプ別の汎用テキストにしています。
あとで中身だけ差し替えればOK。
"""


# 12星座（日本語名）
FIRE_SIGNS = ["牡羊座", "獅子座", "射手座"]
EARTH_SIGNS = ["牡牛座", "乙女座", "山羊座"]
AIR_SIGNS = ["双子座", "天秤座", "水瓶座"]
WATER_SIGNS = ["蟹座", "蠍座", "魚座"]

ALL_SIGNS = FIRE_SIGNS + EARTH_SIGNS + AIR_SIGNS + WATER_SIGNS


# ---------------- 太陽：価値観の違いテキスト ----------------

SUN_TEXT_GENERIC = (
    "{your_name} さんと {partner_name} さんは、太陽サインの違いから "
    "「大事にしたい価値観」の重心が少しずつ異なるペアです。"
    "片方は安定や責任感を、もう片方は変化やワクワク感を求めやすく、"
    "お金の使い方や休日の過ごし方など、小さな場面で違いが出やすくなります。"
    "ただ、その違いはぶつかるためではなく、お互いの世界を広げ合うためのコントラストでもあります。"
    "どちらかに寄せすぎるのではなく、「今日はどちらの価値観を優先するか」を相談して決めていくことで、"
    "二人なりのちょうどいいバランスが見えてきます。"
)

# ここでは12星座すべて同じ文章を使うが、あとで星座ごとに差し替え可能
SUN_TEMPLATES = {sign: SUN_TEXT_GENERIC for sign in ALL_SIGNS}


# ---------------- 月：感情と安心ポイントの違い ----------------

MOON_TEXT_GENERIC = (
    "月サインは「素の感情」と「安心できるポイント」を表します。"
    "{your_name} さんと {partner_name} さんは、感情の受け取り方や、"
    "落ち着ける距離感が少し違う組み合わせです。"
    "片方は静かな時間や落ち着いたペースに安心し、"
    "もう片方はその場で気持ちを共有することで心がほぐれていきます。"
    "どちらが正しいということではなく、安心の形が違うだけです。"
    "「今日は聞いてほしいのか」「そっとしておいてほしいのか」を一言だけ伝え合えると、"
    "すれ違いがぐっと減り、感情面の信頼が深まっていきます。"
)

MOON_TEMPLATES = {sign: MOON_TEXT_GENERIC for sign in ALL_SIGNS}


# ---------------- ASC：第一印象＆ふたりの雰囲気 ----------------

ASC_TEXT_SOFT = (
    "ASC（アセンダント）は、第一印象やふたりの雰囲気を表します。"
    "{your_name} さんと {partner_name} さんの組み合わせは、"
    "周りから見ると「穏やかで話しやすいペア」という印象になりやすいタイプです。"
    "ゆるやかな空気感の中で少しずつ距離を縮めていくため、"
    "出会ってから時間をかけて関係が深まっていく傾向があります。"
)

ASC_TEXT_ACTIVE = (
    "ASC（アセンダント）は、第一印象やふたりの雰囲気を表します。"
    "{your_name} さんと {partner_name} さんの組み合わせは、"
    "周りから見ると「明るくて行動力のあるペア」という印象になりやすいタイプです。"
    "一緒に動くほど距離が縮まりやすく、共通の体験がそのまま思い出になっていきます。"
)

ASC_TEXT_BALANCED = (
    "ASC（アセンダント）は、第一印象やふたりの雰囲気を表します。"
    "{your_name} さんと {partner_name} さんの組み合わせは、"
    "落ち着きと柔らかさのバランスがよく、場面によって空気を読みながら "
    "雰囲気を変えていけるペアです。"
    "状況に合わせて役割を切り替えられるため、長く付き合うほど居心地がよくなっていきます。"
)

ASC_TEXT_DEEP = (
    "ASC（アセンダント）は、第一印象やふたりの雰囲気を表します。"
    "{your_name} さんと {partner_name} さんの組み合わせは、"
    "静かだけれど深い信頼を育てていくペアです。"
    "外からはあまり見えないところで理解が深まりやすく、"
    "時間をかけて「二人だけの世界観」ができていきます。"
)

# ASC 用の4タイプ（ラベルだけ。実際の割り当てロジックは後で詳細化してOK）
ASC_TYPES = {
    "soft": ASC_TEXT_SOFT,
    "active": ASC_TEXT_ACTIVE,
    "balanced": ASC_TEXT_BALANCED,
    "deep": ASC_TEXT_DEEP,
}


def _render(text: str,
            your_name: str,
            partner_name: str,
            your_sign: str,
            partner_sign: str) -> str:
    """
    テンプレ内の {your_name} などを実際の値に差し替える。
    （今は sign を文章中で使っていないが、あとで修正しやすいように渡しておく）
    """
    return text.format(
        your_name=your_name,
        partner_name=partner_name,
        your_sign=your_sign,
        partner_sign=partner_sign,
    )


def _pick_asc_type(your_asc: str, partner_asc: str) -> str:
    """
    ASC を4タイプにざっくり分類するための簡易ロジック。
    ここもあとで細かく調整してOK。
    """
    # ざっくり：火・風 = active / 土 = deep / 水 = soft / その他 = balanced
    if your_asc in FIRE_SIGNS or partner_asc in FIRE_SIGNS:
        return "active"
    if your_asc in AIR_SIGNS or partner_asc in AIR_SIGNS:
        return "balanced"
    if your_asc in WATER_SIGNS or partner_asc in WATER_SIGNS:
        return "soft"
    # 残り（土要素など）
    return "deep"


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
    Page3 Aプラン用：
    太陽（価値観）・月（感情）・ASC（雰囲気）の3つの文章ブロックを返す。
    """

    # 太陽ブロック
    sun_tpl = SUN_TEMPLATES.get(your_sun, SUN_TEXT_GENERIC)
    sun_block = _render(sun_tpl, your_name, partner_name, your_sun, partner_sun)

    # 月ブロック
    moon_tpl = MOON_TEMPLATES.get(your_moon, MOON_TEXT_GENERIC)
    moon_block = _render(moon_tpl, your_name, partner_name, your_moon, partner_moon)

    # ASCブロック（4タイプのどれかを選ぶ）
    asc_type_key = _pick_asc_type(your_asc, partner_asc)
    asc_tpl = ASC_TYPES.get(asc_type_key, ASC_TEXT_BALANCED)
    asc_block = _render(asc_tpl, your_name, partner_name, your_asc, partner_asc)

    return {
        "sun_block": sun_block,
        "moon_block": moon_block,
        "asc_block": asc_block,
    }

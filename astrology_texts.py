# astrology_texts.py
# 占星レポート用のテキスト辞書をまとめるファイル

SUN_PAIR_TEXTS = {
    # 例：太陽 火 × 火
    "fire_fire": "ふたりは勢いと明るさが重なる組み合わせ。決断も早く、前向きな流れを作りやすい相性です。",
}

MOON_PAIR_TEXTS = {
    # 例：月 水 × 水
    "water_water": "どちらも感受性が強く、気持ちが自然と伝わりやすい組み合わせ。言葉より雰囲気で通じ合います。",
}

ASC_PAIR_TEXTS = {
    # 例：上昇 外向 × 外向
    "extro_extro": "明るく社交的な印象が重なり、初対面から距離が縮まりやすいコンビです。",
}

PAGE3_CORE_TEXTS = {
    # ---- 4タイプ：やさしさ型 ----
    "warm": (
        "ふたりの関係には、安心感と落ち着きが自然に流れています。\n"
        "お互いのちがいをやわらかく受け止めながら、穏やかなペースで前に進んでいける相性です。\n"
        "話し合うときも衝突より理解が先に立ち、長く続く関係を育てやすい組み合わせです。"
    ),

    # ---- 4タイプ：刺激・情熱型 ----
    "fire": (
        "ふたりの関係には、刺激と前向きな勢いがあふれています。\n"
        "行動力が重なり、短い時間で一気に距離が縮まりやすい相性です。\n"
        "ときに熱くなりすぎる面もありますが、そのぶん情熱と活力がふたりを強く結びつけます。"
    ),

    # ---- 4タイプ：思考・距離感重視型 ----
    "air": (
        "ふたりの関係は、さっぱりとした心地よさと自由さを大切にする相性です。\n"
        "互いの価値観や考え方に興味を持ち、会話を通して深い理解が育ちます。\n"
        "ほどよい距離感があることで、無理なく自然体でいられる関係です。"
    ),

    # ---- 4タイプ：安定・継続型 ----
    "earth": (
        "ふたりの関係は、信頼と安定感を軸にしっかり育っていく相性です。\n"
        "ゆっくりでも着実に絆が深まり、長期的なパートナーシップに向く組み合わせです。\n"
        "現実的に支え合えるため、生活面でも相性の良さを実感しやすい関係です。"
    ),
}

# =========================
# Page3 用 变量模板（正式版）
# =========================

# 关系的基调（総合印象 / 基本テーマ）
CORE_PAIR_OVERVIEW = {
    "fire_fire": "",
    "fire_earth": "",
    "fire_air": "",
    "fire_water": "",
    "earth_earth": "",
    "earth_air": "",
    "earth_water": "",
    "air_air": "",
    "air_water": "",
    "water_water": "",
}

# 太陽 × 太陽（本質 / 価値観）
SUN_PAIR_TEXTS = {
    "fire_fire": "",
    "fire_earth": "",
    "fire_air": "",
    "fire_water": "",
    "earth_earth": "",
    "earth_air": "",
    "earth_water": "",
    "air_air": "",
    "air_water": "",
    "water_water": "",
}

# 月 × 月（感情テンポ）
MOON_PAIR_TEXTS = {
    "fire_fire": "",
    "fire_earth": "",
    "fire_air": "",
    "fire_water": "",
    "earth_earth": "",
    "earth_air": "",
    "earth_water": "",
    "air_air": "",
    "air_water": "",
    "water_water": "",
}

# ASC × ASC（第一印象 / 外向特質）
ASC_PAIR_TEXTS = {
    "extro_extro": "",
    "extro_stable": "",
    "extro_soft": "",
    "stable_stable": "",
    "stable_soft": "",
    "soft_soft": "",
}

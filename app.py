from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import io
import os
import datetime
import math
from astrology_texts import (
    SUN_PAIR_TEXTS,
    MOON_PAIR_TEXTS,
    ASC_PAIR_TEXTS,
    PAGE4_CORE_PAIR_TEXTS,
    VENUS_PAIR_TEXTS,
    MOON_VENUS_TEXTS,
    PAGE4_HIGHLIGHTS,
    PAGE4_TALK_INTRO,
    PAGE4_PROBLEM_INTRO,
    PAGE4_VALUES_INTRO,
    MARS_PAIR_TEXTS,
    CONFLICT_STYLE_TEXTS,
    DRIVE_BALANCE_TEXTS,
    VENUS_LIFESTYLE_TEXTS,
    SUN_VENUS_TEXTS,
    LIFESTYLE_DETAIL_TEXTS,
    RELATION_THEME_TEXTS,
    RELATION_CHALLENGE_TEXTS,
    RELATION_KEYWORD_TEXTS,
    PAGE8_SUMMARY_MAIN,
    PAGE8_HIGHLIGHTS,
    PAGE8_PITFALLS,
    PAGE8_FINAL_ADVICE,
)


# ==== Swiss Ephemeris 设置 ====
import swisseph as swe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EPHE_PATH = os.path.join(BASE_DIR, "ephe")
swe.set_ephe_path(EPHE_PATH)

HAS_SWISSEPH = True

# ------------------------------------------------------------------
# Flask 基本设置：public 目录作为静态目录
# ------------------------------------------------------------------
app = Flask(__name__, static_url_path="", static_folder="public")

# ------------------------------------------------------------------
# 占星符号数组 + lon → 星座函数
# ------------------------------------------------------------------
ZODIAC_SIGNS = [
    "牡羊座", "牡牛座", "双子座", "蟹座",
    "獅子座", "乙女座", "天秤座", "蠍座",
    "射手座", "山羊座", "水瓶座", "魚座",
]


def lon_to_sign(lon):
    """支持 float / tuple / list 的安全版"""
    if isinstance(lon, (tuple, list)):
        lon = lon[0]
    lon = float(lon)
    idx = int(lon // 30) % 12
    return ZODIAC_SIGNS[idx]


# ------------------------------------------------------------------
# 备用：简单假算法（swisseph 失败时兜底）
# ------------------------------------------------------------------
def compute_simple_signs(birth_date, birth_time):
    try:
        y, m, d = [int(x) for x in birth_date.split("-")]
    except Exception:
        y, m, d = 1990, 1, 1

    try:
        hh, mm = [int(x) for x in birth_time.split(":")]
    except Exception:
        hh, mm = 12, 0

    seed = (y * 1231 + m * 97 + d * 13 + hh * 7 + mm) % 360

    def fake(offset):
        idx = ((seed + offset) % 360) // 30
        return ZODIAC_SIGNS[int(idx)]

    return {
        "sun": fake(0),
        "moon": fake(40),
        "asc": fake(80),
        "venus": fake(160),
        "mars": fake(220),
    }


# ------------------------------------------------------------------
# 真实星盘：统一入口（瑞士星历）
# ------------------------------------------------------------------
def compute_core_from_birth(dob_str, time_str, place_name):
    """
    使用 Swiss Ephemeris 计算
    太阳 / 月亮 / 金星 / 火星 / ASC 的度数和星座名（日文）
    """

    # 1. 日期
    try:
        year, month, day = [int(x) for x in dob_str.split("-")]
    except Exception:
        year, month, day = 1990, 1, 1

    # 2. 时间（日本本地时间 → UT）
    try:
        hh, mm = [int(x) for x in time_str.split(":")]
    except Exception:
        hh, mm = 12, 0

    local_hour = hh + mm / 60.0      # JST
    ut_hour = local_hour - 9.0       # UTC

    # 3. 经纬度（统一用东京）
    lat = 35.6895
    lon = 139.6917

    # 4. 儒略日（UT）
    jd = swe.julday(year, month, day, ut_hour)

    try:
        # 5. 行星黄经
        sun_lon = swe.calc_ut(jd, swe.SUN)[0]
        moon_lon = swe.calc_ut(jd, swe.MOON)[0]
        venus_lon = swe.calc_ut(jd, swe.VENUS)[0]
        mars_lon = swe.calc_ut(jd, swe.MARS)[0]

        # 6. ASC（House 计算）
        houses, ascmc = swe.houses(jd, lat, lon)
        asc_lon = ascmc[0]

        core = {
            "sun": {"lon": sun_lon, "sign_jp": lon_to_sign(sun_lon)},
            "moon": {"lon": moon_lon, "sign_jp": lon_to_sign(moon_lon)},
            "venus": {"lon": venus_lon, "sign_jp": lon_to_sign(venus_lon)},
            "mars": {"lon": mars_lon, "sign_jp": lon_to_sign(mars_lon)},
            "asc": {"lon": asc_lon, "sign_jp": lon_to_sign(asc_lon)},
        }

        # 扁平别名字段（兼容其他地方）
        core["sun_deg"] = sun_lon
        core["moon_deg"] = moon_lon
        core["venus_deg"] = venus_lon
        core["mars_deg"] = mars_lon
        core["asc_deg"] = asc_lon

        core["sun_sign_jp"] = core["sun"]["sign_jp"]
        core["moon_sign_jp"] = core["moon"]["sign_jp"]
        core["venus_sign_jp"] = core["venus"]["sign_jp"]
        core["mars_sign_jp"] = core["mars"]["sign_jp"]
        core["asc_sign_jp"] = core["asc"]["sign_jp"]

    except Exception:
        # swisseph 出问题就用假算法兜底（只有星座，没有度数）
        fake = compute_simple_signs(dob_str, time_str)
        core = {
            "sun": {"lon": 0.0, "sign_jp": fake["sun"]},
            "moon": {"lon": 0.0, "sign_jp": fake["moon"]},
            "venus": {"lon": 0.0, "sign_jp": fake["venus"]},
            "mars": {"lon": 0.0, "sign_jp": fake["mars"]},
            "asc": {"lon": 0.0, "sign_jp": fake["asc"]},
        }
        core["sun_deg"] = core["moon_deg"] = core["venus_deg"] = core["mars_deg"] = core["asc_deg"] = 0.0
        core["sun_sign_jp"] = core["sun"]["sign_jp"]
        core["moon_sign_jp"] = core["moon"]["sign_jp"]
        core["venus_sign_jp"] = core["venus"]["sign_jp"]
        core["mars_sign_jp"] = core["mars"]["sign_jp"]
        core["asc_sign_jp"] = core["asc"]["sign_jp"]

    return core


# ------------------------------------------------------------------
# 基础目录 & 页面尺寸
# ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "public", "assets")
EPHE_DIR = os.path.join(BASE_DIR, "ephe")

try:
    swe.set_ephe_path(EPHE_DIR)
except Exception:
    HAS_SWISSEPH = False

PAGE_WIDTH, PAGE_HEIGHT = A4

# ------------------------------------------------------------------
# 字体设置
# ------------------------------------------------------------------
JP_SANS = "HeiseiKakuGo-W5"
JP_SERIF = "HeiseiMin-W3"

pdfmetrics.registerFont(UnicodeCIDFont(JP_SANS))
pdfmetrics.registerFont(UnicodeCIDFont(JP_SERIF))

# ★ 新增这一行，让 JP_SANS_BOLD 指向同一个字体（看起来就当作粗体用）
JP_SANS_BOLD = JP_SANS


# ------------------------------------------------------------------
# 小工具：铺满整页背景
# ------------------------------------------------------------------
def draw_full_bg(c, filename):
    path = os.path.join(ASSETS_DIR, filename)
    img = ImageReader(path)
    c.drawImage(img, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)


# ------------------------------------------------------------------
# 小工具：日期格式化 YYYY-MM-DD → 2025年11月13日
# ------------------------------------------------------------------
def get_display_date(raw_date: str | None) -> str:
    if raw_date:
        try:
            d = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            d = datetime.date.today()
    else:
        d = datetime.date.today()
    return f"{d.year}年{d.month}月{d.day}日"


# ------------------------------------------------------------------
# 小工具：极坐标 → 直角坐标（0° 在 12 点方向，逆时针）
# ------------------------------------------------------------------
def polar_to_xy(cx, cy, radius, angle_deg):
    theta = math.radians(90 - angle_deg)
    x = cx + radius * math.cos(theta)
    y = cy + radius * math.sin(theta)
    return x, y


# ------------------------------------------------------------------
# 小工具：在星盘上画「彩色点 + PNG 图标」
# ------------------------------------------------------------------
def draw_planet_icon(
    c,
    cx,
    cy,
    chart_size,
    angle_deg,
    color_rgb,
    icon_filename,
):
    r_dot = chart_size * 0.34
    r_icon = chart_size * 0.28

    px, py = polar_to_xy(cx, cy, r_dot, angle_deg)
    r, g, b = color_rgb
    c.setFillColorRGB(r, g, b)
    c.circle(px, py, 2.3, fill=1, stroke=0)

    ix, iy = polar_to_xy(cx, cy, r_icon, angle_deg)
    icon_path = os.path.join(ASSETS_DIR, icon_filename)
    icon_img = ImageReader(icon_path)
    icon_size = 11

    c.drawImage(
        icon_img,
        ix - icon_size / 2,
        iy - icon_size / 2,
        width=icon_size,
        height=icon_size,
        mask="auto",
    )


# ------------------------------------------------------------------
# 小工具：文本自动换行
# ------------------------------------------------------------------
def draw_wrapped_block(c, text, x, y_start, wrap_width,
                       font_name, font_size, line_height):
    c.setFont(font_name, font_size)
    line = ""
    y = y_start

    for ch in text:
        if ch == "\n":
            c.drawString(x, y, line)
            line = ""
            y -= line_height
            continue

        new_line = line + ch
        if pdfmetrics.stringWidth(new_line, font_name, font_size) <= wrap_width:
            line = new_line
        else:
            c.drawString(x, y, line)
            line = ch
            y -= line_height

    if line:
        c.drawString(x, y, line)
        y -= line_height

    return y

def split_sentences_jp(text: str):
    """日文テキストを「。」「！」「？」などでざっくり文単位に分割"""
    if not text:
        return []
    sentences = []
    buf = []
    for ch in text:
        buf.append(ch)
        if ch in "。！？!?":
            s = "".join(buf).strip()
            if s:
                sentences.append(s)
            buf = []
    if buf:
        s = "".join(buf).strip()
        if s:
            sentences.append(s)
    return sentences


def trim_text_for_box(text: str, max_lines: int, chars_per_line: int) -> str:
    """
    「最大行数 × 1行あたりの目安文字数」で収まるようにテキストを前から切り出す。
    ・文単位でできるだけきれいに区切る
    ・どうしても1文が長すぎる場合は、その文を途中まで切る
    """
    if not text:
        return ""

    max_chars = max_lines * chars_per_line

    # そもそも全体が収まるならそのまま返す
    if len(text) <= max_chars:
        return text

    sentences = split_sentences_jp(text)
    if not sentences:
        # 文分割できなかった場合は生テキストを強制的に切る
        return text[:max_chars]

    result_parts = []
    total = 0

    for s in sentences:
        s_len = len(s)
        # まだ何も入ってない状態で1文が箱より大きい場合 → その文を途中で切る
        if not result_parts and s_len > max_chars:
            return s[:max_chars]

        # すでに何文か入っていて、次を足すとはみ出す → ここで終了
        if total + s_len > max_chars:
            break

        result_parts.append(s)
        total += s_len

        if total >= max_chars:
            break

    if not result_parts:
        # 念のための保険
        return text[:max_chars]

    return "".join(result_parts)


# ------------------------------------------------------------------
# 行数限制版：最多画 max_lines 行
# ------------------------------------------------------------------
def draw_wrapped_block_limited(
    c,
    text,
    x,
    y_start,
    wrap_width,
    font_name,
    font_size,
    line_height,
    max_lines,
):
    c.setFont(font_name, font_size)
    line = ""
    y = y_start
    lines = 0

    for ch in text:
        if ch == "\n":
            c.drawString(x, y, line)
            line = ""
            y -= line_height
            lines += 1
            if lines >= max_lines:
                return y
            continue

        new_line = line + ch
        if pdfmetrics.stringWidth(new_line, font_name, font_size) <= wrap_width:
            line = new_line
        else:
            c.drawString(x, y, line)
            line = ch
            y -= line_height
            lines += 1
            if lines >= max_lines:
                return y

    if line and lines < max_lines:
        c.drawString(x, y, line)
        y -= line_height

    return y


# ------------------------------------------------------------------
# 小工具：页码（从第 3 页开始用）
# ------------------------------------------------------------------
def draw_page_number(c, page_num: int):
    c.setFont(JP_SANS, 10)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawCentredString(PAGE_WIDTH / 2, 40, str(page_num))

# ==============================================================
#                    第 3〜7 页：页面绘制函数
# ==============================================================

# ------------------------------------------------------------------
# Page3 用：相性テキスト + 太陽・月・ASC のテキスト + 星盤描画
# ------------------------------------------------------------------

# 12星座 → 4元素
SIGN_ELEMENT = {
    "牡羊座": "fire",
    "牡牛座": "earth",
    "双子座": "air",
    "蟹座":   "water",
    "獅子座": "fire",
    "乙女座": "earth",
    "天秤座": "air",
    "蠍座":   "water",
    "射手座": "fire",
    "山羊座": "earth",
    "水瓶座": "air",
    "魚座":   "water",
}

# 元素の組み合わせごとの相性まとめ（2文以内）
PAIR_SUMMARY_TEXT = {
    ("fire", "fire"):
        "情熱と勢いで惹かれ合う、華やかなペアです。"
        "お互いが主役になりやすいので、ときどきペースを落として相手の気持ちを聞けると長続きします。",
    ("fire", "earth"):
        "片方の情熱と片方の安定感が、良いバランスを生み出すペアです。"
        "勢いだけで突っ走らず、現実的な計画を一緒に立てることで関係が育ちやすくなります。",
    ("fire", "air"):
        "ノリとアイデアで世界を広げていける、刺激的なペアです。"
        "その場の勢いで決めすぎず、ときどき未来のビジョンをすり合わせると安心感も高まります。",
    ("fire", "water"):
        "情熱と感受性が混ざり合う、ドラマチックなペアです。"
        "感情がぶつかりやすいぶん、相手のペースを尊重してあげると深い信頼につながります。",
    ("earth", "fire"):
        "堅実さと行動力で、現実をしっかり動かしていけるペアです。"
        "慎重さとチャレンジ精神の両方を大事にすると、長期的なパートナーシップになりやすいタイプです。",
    ("earth", "earth"):
        "価値観や生活リズムが似やすい、安心感の高いペアです。"
        "安定を大切にしつつ、ときどき小さな変化や楽しみを共有するとマンネリを防げます。",
    ("earth", "air"):
        "片方が現実を支え、片方が視野を広げる、補い合いのペアです。"
        "考え方の違いを否定せず、「役割分担」として受け止めると心地よい距離感が育ちます。",
    ("earth", "water"):
        "現実感と優しさで、ほっとできる居場所をつくれるペアです。"
        "感情を我慢しすぎず、素直な気持ちを言葉にすることで、さらに信頼が深まっていきます。",
    ("air", "fire"):
        "会話と行動力で世界をどんどん広げていける、冒険タイプのペアです。"
        "テンションの差が出たときは、相手のモードを確認してから動くとすれ違いが減ります。",
    ("air", "earth"):
        "アイデアと現実性を組み合わせて、着実に形にできるペアです。"
        "理屈と感覚の両方を尊重しながら話し合うことで、安定と自由のバランスが整っていきます。",
    ("air", "air"):
        "価値観や会話のテンポが似やすく、一緒にいて気楽なペアです。"
        "話すだけで終わらず、小さな約束を実行していくと信頼感がより強くなります。",
    ("air", "water"):
        "片方が言葉で整理し、片方が気持ちで寄り添う、心のサポート力の高いペアです。"
        "感情と理性のギャップを責め合わず、「お互いの強み」として活かすと絆が深まります。",
    ("water", "fire"):
        "感情の深さと情熱が混ざり合う、印象的なペアです。"
        "ムードに流されすぎず、安心できるルールやペースを共有すると長く続きやすくなります。",
    ("water", "earth"):
        "優しさと安定感で、落ち着いた関係を育てていけるペアです。"
        "気遣いで我慢しすぎず、ときどき本音を打ち明けることで心の距離がさらに縮まります。",
    ("water", "air"):
        "感性と知性がお互いを刺激し合う、化学反応タイプのペアです。"
        "感じ方の違いを説明し合う時間をつくると、誤解が減って支え合いやすくなります。",
    ("water", "water"):
        "感情の波を分かち合える、共感力の高いペアです。"
        "ふたりとも疲れているときは、言葉より休息を優先するなど、セルフケアを共有できると安心感が続きます。",
}

def build_pair_summary_from_sun(your_sun_ja: str, partner_sun_ja: str) -> str:
    em = SIGN_ELEMENT.get(your_sun_ja)
    ep = SIGN_ELEMENT.get(partner_sun_ja)
    if em is None or ep is None:
        return (
            "お互いの違いを通して、新しい価値観を学び合えるペアです。"
            "少しずつ歩調を合わせていくことで、安心できる関係が育っていきます。"
        )
    base = PAIR_SUMMARY_TEXT.get((em, ep))
    if base is None:
        return (
            "お互いの個性を活かしながら、ほどよい距離感で支え合えるペアです。"
            "違いを否定せず、興味を持って聞き合うことで信頼が深まります。"
        )
    return base

def build_page3_texts(
    your_name: str,
    partner_name: str,
    your_core: dict,
    partner_core: dict,
):
    def get_sign_name(core: dict, key: str) -> str:
        v = core.get(key)
        if isinstance(v, dict):
            return (
                v.get("name_ja")
                or v.get("sign_jp")
                or v.get("label")
                or ""
            )
        return str(v) if v is not None else ""

    # 元の太陽組み合わせサマリー（既存ロジックそのまま）
    your_sun = your_core.get("sun_sign_jp") or get_sign_name(your_core, "sun")
    partner_sun = partner_core.get("sun_sign_jp") or get_sign_name(partner_core, "sun")
    compat_text = build_pair_summary_from_sun(your_sun, partner_sun)

    # 星座 → 4元素に変換
    def sign_to_element(sign_jp: str) -> str:
        if not sign_jp:
            return ""
        s = str(sign_jp)
        if ("牡羊" in s) or ("獅子" in s) or ("射手" in s):
            return "fire"
        if ("牡牛" in s) or ("乙女" in s) or ("山羊" in s):
            return "earth"
        if ("双子" in s) or ("天秤" in s) or ("水瓶" in s):
            return "air"
        if ("蟹" in s) or ("蠍" in s) or ("魚" in s):
            return "water"
        return ""

    # 4元素ペア → fire_earth 形式のキーに変換
    def make_element_pair_key(e1: str, e2: str) -> str:
        if not e1 or not e2:
            return ""
        if e1 == e2:
            return f"{e1}_{e2}"
        order = {"fire": 0, "earth": 1, "air": 2, "water": 3}
        a, b = sorted([e1, e2], key=lambda x: order.get(x, 99))
        return f"{a}_{b}"

    # ASC 星座 → 3タイプ（extro / stable / soft）
    def asc_to_group(sign_jp: str) -> str:
        if not sign_jp:
            return "stable"
        s = str(sign_jp)
        # 外向・動きのある印象
        if ("牡羊" in s) or ("双子" in s) or ("獅子" in s) or ("天秤" in s) or ("射手" in s) or ("水瓶" in s):
            return "extro"
        # 落ち着き・現実感
        if ("牡牛" in s) or ("乙女" in s) or ("山羊" in s):
            return "stable"
        # やわらかさ・共感
        if ("蟹" in s) or ("蠍" in s) or ("魚" in s):
            return "soft"
        return "stable"

    # ASC グループペア → extro_soft 形式キー
    def make_asc_pair_key(g1: str, g2: str) -> str:
        if not g1 or not g2:
            return ""
        if g1 == g2:
            return f"{g1}_{g2}"
        order = {"extro": 0, "stable": 1, "soft": 2}
        a, b = sorted([g1, g2], key=lambda x: order.get(x, 99))
        return f"{a}_{b}"

    # 太陽・月・ASC からキーを作成
    your_sun_el = sign_to_element(your_core.get("sun_sign_jp") or get_sign_name(your_core, "sun"))
    partner_sun_el = sign_to_element(partner_core.get("sun_sign_jp") or get_sign_name(partner_core, "sun"))
    sun_key = make_element_pair_key(your_sun_el, partner_sun_el)

    your_moon_el = sign_to_element(your_core.get("moon_sign_jp") or get_sign_name(your_core, "moon"))
    partner_moon_el = sign_to_element(partner_core.get("moon_sign_jp") or get_sign_name(partner_core, "moon"))
    moon_key = make_element_pair_key(your_moon_el, partner_moon_el)

    your_asc_group = asc_to_group(your_core.get("asc_sign_jp") or get_sign_name(your_core, "asc"))
    partner_asc_group = asc_to_group(partner_core.get("asc_sign_jp") or get_sign_name(partner_core, "asc"))
    asc_key = make_asc_pair_key(your_asc_group, partner_asc_group)

    # Page3 用テキスト
    sun_text = SUN_PAIR_TEXTS.get(sun_key, "")
    moon_text = MOON_PAIR_TEXTS.get(moon_key, "")
    asc_text = ASC_PAIR_TEXTS.get(asc_key, "")

    return compat_text, sun_text, moon_text, asc_text


# 星盤データ構造（実際の度数を使う）
def build_planet_block(core: dict) -> dict:
    def fmt(label_ja: str, d) -> str:
        if isinstance(d, dict):
            name = (
                d.get("name_ja")
                or d.get("sign_jp")
                or d.get("label")
                or ""
            )
        else:
            name = str(d) if d is not None else ""
        return f"{label_ja}：{name}"

    def deg_from(core_obj) -> float:
        """core_obj['lon'] 可能是 float，也可能是 (float, ...) tuple，这里统一取第 0 个并转成 float。"""
        if isinstance(core_obj, dict):
            v = core_obj.get("lon")
        else:
            v = core_obj
        if isinstance(v, (tuple, list)):
            v = v[0]
        return float(v)

    return {
        "sun": {
            "deg": deg_from(core["sun"]),
            "label": fmt("太陽", core["sun"]),
        },
        "moon": {
            "deg": deg_from(core["moon"]),
            "label": fmt("月", core["moon"]),
        },
        "venus": {
            "deg": deg_from(core["venus"]),
            "label": fmt("金星", core["venus"]),
        },
        "mars": {
            "deg": deg_from(core["mars"]),
            "label": fmt("火星", core["mars"]),
        },
        "asc": {
            "deg": deg_from(core["asc"]),
            "label": fmt("ASC", core["asc"]),
        },
    }  


def draw_page3_basic_and_synastry(
    c,
    your_name: str,
    partner_name: str,
    your_core: dict,
    partner_core: dict,
    compat_text: str,
    sun_text: str,
    moon_text: str,
    asc_text: str,
):
    # 背景
    draw_full_bg(c, "page_basic.jpg")

    # 星盤ベース画像
    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    chart_size = 180
    left_x = 90
    left_y = 520
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    left_cx = left_x + chart_size / 2
    left_cy = left_y + chart_size / 2
    right_cx = right_x + chart_size / 2
    right_cy = right_y + chart_size / 2

    # 左右の星盤
    c.drawImage(
        chart_img,
        left_x,
        left_y,
        width=chart_size,
        height=chart_size,
        mask="auto",
    )
    c.drawImage(
        chart_img,
        right_x,
        right_y,
        width=chart_size,
        height=chart_size,
        mask="auto",
    )

    # 惑星度数・ラベル
    your_planets = build_planet_block(your_core)
    partner_planets = build_planet_block(partner_core)

    icon_files = {
        "sun": "icon_sun.png",
        "moon": "icon_moon.png",
        "venus": "icon_venus.png",
        "mars": "icon_mars.png",
        "asc": "icon_asc.png",
    }

    your_color = (0.15, 0.45, 0.9)
    partner_color = (0.9, 0.35, 0.65)

    # 惑星アイコン描画
    for key, info in your_planets.items():
        draw_planet_icon(
            c,
            left_cx,
            left_cy,
            chart_size,
            info["deg"],
            your_color,
            icon_files[key],
        )

    for key, info in partner_planets.items():
        draw_planet_icon(
            c,
            right_cx,
            right_cy,
            chart_size,
            info["deg"],
            partner_color,
            icon_files[key],
        )

    # 名前
    c.setFont(JP_SERIF, 14)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(left_cx, left_y - 25, f"{your_name} さん")
    c.drawCentredString(right_cx, right_y - 25, f"{partner_name} さん")

    # 惑星ラベル
    c.setFont(JP_SERIF, 8.5)
    your_lines = [info["label"] for info in your_planets.values()]
    for i, line in enumerate(your_lines):
        y = left_y - 45 - i * 11
        c.drawString(left_cx - 30, y, line)

    partner_lines = [info["label"] for info in partner_planets.values()]
    for i, line in enumerate(partner_lines):
        y = right_y - 45 - i * 11
        c.drawString(right_cx - 30, y, line)

    # ===== Page3 下部テキスト（タイトルなし・本文だけ） =====
    text_x = 120
    wrap_width = 400
    body_font = JP_SERIF
    body_size = 12      # 正文字号固定 12pt
    line_height = 18

    # ---------- 第1ブロック：ふたりの相性バランス（少し上に） ----------
    y_first = 350  # ← 第1块整体往上移，高一点
    y = draw_wrapped_block_limited(
        c,
        compat_text,
        text_x,
        y_first,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=3,
    )

    # ---------- 第2〜4ブロック：太陽 / 月 / ASC（第1块の下にまとめて配置） ----------
    y = 240  # ← 后三块的起点：整体往下拉开一点距离

    for block_text in (sun_text, moon_text, asc_text):
        y = draw_wrapped_block_limited(
            c,
            block_text,
            text_x,
            y,
            wrap_width,
            body_font,
            body_size,
            line_height,
            max_lines=3,
        )
        y -= line_height * 1.4  # ← 区块间距比以前大一点

    draw_page_number(c, 3)
    c.showPage()



# ------------------------------------------------------------------
# Page4〜7 用：文案生成函数（先用固定文案占位，后面你再换成 AI 版本）
# ------------------------------------------------------------------

def build_page4_texts(your_name, partner_name, your_core, partner_core):
    """コミュニケーションページ用テキスト（完全動的版）

    Page4 タイトル：
    ① 会話の方向性
    ② 暖かいポイント / すれ違いポイント
    ③ 価値観・対話スタイル
    """

    # --- 共通ヘルパー：星座名 → 4元素 / サイン取得 ---
    def get_sign(core: dict, key: str) -> str:
        """core から sign_jp を安全に取り出す（なければ name_ja / label を見る）"""
        # 先にフラットフィールド（sun_sign_jp など）を優先
        flat = core.get(f"{key}_sign_jp")
        if flat:
            return str(flat)
        v = core.get(key)
        if isinstance(v, dict):
            return (
                v.get("sign_jp")
                or v.get("name_ja")
                or v.get("label")
                or ""
            )
        return str(v) if v is not None else ""

    def sign_to_element(sign_jp: str) -> str:
        if not sign_jp:
            return ""
        s = str(sign_jp)
        if ("牡羊" in s) or ("獅子" in s) or ("射手" in s):
            return "fire"
        if ("牡牛" in s) or ("乙女" in s) or ("山羊" in s):
            return "earth"
        if ("双子" in s) or ("天秤" in s) or ("水瓶" in s):
            return "air"
        if ("蟹" in s) or ("蠍" in s) or ("魚" in s):
            return "water"
        return ""

    def make_element_pair_key(e1: str, e2: str) -> str:
        """fire_earth / air_air みたいなキーを作る"""
        if not e1 or not e2:
            return ""
        if e1 == e2:
            return f"{e1}_{e2}"
        order = {"fire": 0, "earth": 1, "air": 2, "water": 3}
        a, b = sorted([e1, e2], key=lambda x: order.get(x, 99))
        return f"{a}_{b}"

    # --- 1) 感情の方向性：太陽の 4元素ペアをベースに ---
    your_sun_el = sign_to_element(get_sign(your_core, "sun"))
    partner_sun_el = sign_to_element(get_sign(partner_core, "sun"))
    core_pair_key = make_element_pair_key(your_sun_el, partner_sun_el)
    core_pair_text = PAGE4_CORE_PAIR_TEXTS.get(core_pair_key, "")

    # --- 2) 親密さの好み：金星 × 金星 の 4元素ペア ---
    your_venus_el = sign_to_element(get_sign(your_core, "venus"))
    partner_venus_el = sign_to_element(get_sign(partner_core, "venus"))
    venus_pair_key = make_element_pair_key(your_venus_el, partner_venus_el)
    venus_pair_text = VENUS_PAIR_TEXTS.get(venus_pair_key, "")

    # --- 3) 月 × 金星（感情テンポ × 愛情スタイル）---
    your_moon_el = sign_to_element(get_sign(your_core, "moon"))
    partner_moon_el = sign_to_element(get_sign(partner_core, "moon"))

    # 両方の Moon / Venus が同じ元素ならその元素、それ以外は mixed として扱う
    moon_venus_key = "mixed"
    for el in ("fire", "earth", "air", "water"):
        if (
            your_moon_el == el
            and partner_moon_el == el
            and your_venus_el == el
            and partner_venus_el == el
        ):
            moon_venus_key = f"{el}_{el}"
            break

    moon_venus_text = MOON_VENUS_TEXTS.get(moon_venus_key, "")

    # =========================
    # ① 会話の方向性（イントロ + core_pair + venus_pair）
    # =========================
    talk_text = (
        PAGE4_TALK_INTRO
        + core_pair_text
        + venus_pair_text
    )
    # ※ サマリーは短いキーワードとして固定フレーズでも OK（本文は完全に動的）
    talk_summary = "会話のテンポや感情表現の癖を知るほど、分かり合いやすくなるふたり。"

    # =========================
    # ② 暖かいポイント / すれ違いポイント
    #    （すれ違いのイントロ + gap_point）
    # =========================
    problem_text = (
        PAGE4_PROBLEM_INTRO
        + PAGE4_HIGHLIGHTS.get("gap_point", "")
    )
    problem_summary = "我慢や遠慮をため込まず、小さな違和感のうちに言葉にしていくのがカギ。"

    # =========================
    # ③ 価値観・対話スタイル
    #    （価値観イントロ + moon×venus + warm_point）
    # =========================
    values_text = (
        PAGE4_VALUES_INTRO
        + moon_venus_text
        + PAGE4_HIGHLIGHTS.get("warm_point", "")
    )
    values_summary = "価値観や感じ方の違いを通して、お互いの世界を広げていけるパートナーシップ。"

    return (
        talk_text, talk_summary,
        problem_text, problem_summary,
        values_text, values_summary,
    )



def build_page5_texts(your_name, partner_name, your_core, partner_core):
    """良い点・すれ違い・伸ばせる点ページ用テキスト（動的版）"""

    # ---- 0) 火星の星座 → エレメント ----
    your_mars_sign = your_core.get("mars_sign_jp") or your_core.get("mars", {}).get("sign_jp")
    partner_mars_sign = partner_core.get("mars_sign_jp") or partner_core.get("mars", {}).get("sign_jp")

    your_el = SIGN_ELEMENT.get(your_mars_sign)
    partner_el = SIGN_ELEMENT.get(partner_mars_sign)

    def _pair_key(e1, e2):
        """'fire_earth' みたいなキーを作る（順番をそろえる）"""
        order = {"fire": 0, "earth": 1, "air": 2, "water": 3}
        if e1 is None or e2 is None:
            return None
        if order[e1] > order[e2]:
            e1, e2 = e2, e1
        return f"{e1}_{e2}"

    # ---- 1) 行動スタイル（火星 × 火星）----
    mars_key = _pair_key(your_el, partner_el)
    mars_text = MARS_PAIR_TEXTS.get(
        mars_key,
        "ふたりの行動スタイルには、違いもあれば似ている部分もあり、"
        "そのバランスが関係を前に進める原動力になっていきます。"
    )

    # ---- 2) 衝突スタイル（反応の速さ）----
    def _speed(e):
        if e in ("fire", "air"):
            return "fast"
        if e in ("earth", "water"):
            return "slow"
        return None

    sy = _speed(your_el)
    sp = _speed(partner_el)
    if sy and sp:
        if sy == "fast" and sp == "fast":
            conflict_key = "fast_fast"
        elif sy == "slow" and sp == "slow":
            conflict_key = "slow_slow"
        else:
            conflict_key = "fast_slow"
    else:
        conflict_key = None

    conflict_text = CONFLICT_STYLE_TEXTS.get(
        conflict_key,
        "衝突が起きたときは、どちらが先に反応しやすいか、"
        "どちらが時間をかけて整理するタイプかを意識すると、ぶつかり方が柔らかくなります。"
    )

    # ---- 3) 攻め役 / 受け止め役バランス ----
    def _drive(e):
        if e in ("fire", "earth"):
            return "strong"
        if e in ("air", "water"):
            return "soft"
        return None

    dy = _drive(your_el)
    dp = _drive(partner_el)
    if dy and dp:
        if dy == "strong" and dp == "strong":
            drive_key = "strong_strong"
        elif dy == "soft" and dp == "soft":
            drive_key = "soft_soft"
        else:
            drive_key = "strong_soft"
    else:
        drive_key = None

    drive_text = DRIVE_BALANCE_TEXTS.get(
        drive_key,
        "どちらか一方だけが頑張りすぎないように、役割やペースをときどき見直していくことが、"
        "大きな負担を防ぐ鍵になります。"
    )

    # ---- 4) 3ブロックに組み立て ----
    # good：行動スタイル + 攻め役 / 受け止め役
    good_text = (
        f"{your_name} さんと {partner_name} さんの行動スタイルは、"
        f"{mars_text}{drive_text}"
    )
    good_summary = "行動力とバランス感覚が合わさり、前向きに進んでいけるペアです。"

    # gap：衝突スタイル
    gap_text = conflict_text
    gap_summary = "反応の速さや受け止め方の違いを言葉にすると、すれ違いはぐっと減っていきます。"

    # hint：少しだけ共通ヒント（ここも固定文 + さっきのバランスにリンク）
    hint_text = (
        f"{drive_text}"
        " ときどき役割やペースを振り返りながら、「次はこうしてみよう」と共有していくことで、"
        "無理なく続けられる関係づくりのヒントになります。"
    )
    hint_summary = "衝突のあとに小さな振り返りを重ねるほど、ふたりのペースは自然とそろっていきます。"

    return (
        good_text, good_summary,
        gap_text, gap_summary,
        hint_text, hint_summary,
    )


def build_page6_texts(your_name, partner_name, your_core, partner_core):
    """関係の方向性と今後ページ用テキスト（完全動的版）"""

    # ---------- 共通ヘルパー ----------
    def get_sign(core: dict, key: str) -> str:
        """core から sign_jp を安全に取り出す（なければ name_ja / label を見る）"""
        flat = core.get(f"{key}_sign_jp")
        if flat:
            return str(flat)
        v = core.get(key)
        if isinstance(v, dict):
            return (
                v.get("sign_jp")
                or v.get("name_ja")
                or v.get("label")
                or ""
            )
        return str(v) if v is not None else ""

    def sign_to_element(sign_jp: str) -> str:
        if not sign_jp:
            return ""
        s = str(sign_jp)
        if ("牡羊" in s) or ("獅子" in s) or ("射手" in s):
            return "fire"
        if ("牡牛" in s) or ("乙女" in s) or ("山羊" in s):
            return "earth"
        if ("双子" in s) or ("天秤" in s) or ("水瓶" in s):
            return "air"
        if ("蟹" in s) or ("蠍" in s) or ("魚" in s):
            return "water"
        return ""

    def make_element_pair_key(e1: str, e2: str) -> str:
        """fire_earth / air_air みたいなキーを作る（順番はソート）"""
        if not e1 or not e2:
            return ""
        if e1 == e2:
            return f"{e1}_{e2}"
        order = {"fire": 0, "earth": 1, "air": 2, "water": 3}
        a, b = sorted([e1, e2], key=lambda x: order.get(x, 99))
        return f"{a}_{b}"

    def same_group(e1: str, e2: str) -> bool:
        """火＋風 / 地＋水 を同じグループとして見る簡易判定"""
        if not e1 or not e2:
            return False
        if e1 == e2:
            return True
        group1 = {"fire", "air"}
        group2 = {"earth", "water"}
        if e1 in group1 and e2 in group1:
            return True
        if e1 in group2 and e2 in group2:
            return True
        return False

    def first_sentence(text: str) -> str:
        """日本語文を句点で区切って最初の一文だけ返す"""
        parts = split_sentences_jp(text)
        if parts:
            return parts[0]
        return text[:30]

    # ---------- ここから実際のロジック ----------

    # 金星 → 生活・価値観の相性
    your_venus_el = sign_to_element(get_sign(your_core, "venus"))
    partner_venus_el = sign_to_element(get_sign(partner_core, "venus"))
    venus_key = make_element_pair_key(your_venus_el, partner_venus_el)

    # 太陽 → 生活テンポ
    your_sun_el = sign_to_element(get_sign(your_core, "sun"))
    partner_sun_el = sign_to_element(get_sign(partner_core, "sun"))

    # ---- デフォルト（今までの固定文） ----
    default_theme_text = (
        "このペアのテーマは、「お互いの違いを通して世界を広げていくこと」です。"
        "似ている部分は安心感を、違う部分は新しい視点をもたらしてくれます。"
    )
    default_emotion_text = (
        "感情面では、どちらかが不安になったときに、"
        "もう一方が少し客観的な視点をくれる、そんな支え合い方をしやすいペアです。"
        "弱さを見せ合えるほど、心の距離は近づいていきます。"
    )
    default_style_text = (
        "ふたりのペースは、必ずしも同じではありません。"
        "でもそれは悪いことではなく、「ゆっくり派」と「さっと動く派」が"
        "一緒にいることで、ほどよいスピードが生まれるイメージです。"
    )
    default_future_text = (
        "これからのふたりにとって大切なのは、"
        "将来のイメージをときどき言葉にして共有することです。"
        "すぐに決めなくても、「こんな未来もいいね」と話し合う時間そのものが、"
        "関係を前に進めてくれます。"
    )

    # ---------- ① ペアのテーマ（金星×金星：VENUS_LIFESTYLE_TEXTS） ----------
    theme_text = VENUS_LIFESTYLE_TEXTS.get(venus_key, default_theme_text)
    theme_summary = first_sentence(theme_text)

    # ---------- ② お金・価値観・安心感（LIFESTYLE_DETAIL_TEXTS） ----------
    # お金の感覚：金星どうしが同グループなら match、それ以外は gap
    money_key = "money_match" if same_group(your_venus_el, partner_venus_el) else "money_gap"
    # 時間感覚：太陽どうしが同グループなら match、それ以外は gap
    time_key = "time_match" if same_group(your_sun_el, partner_sun_el) else "time_gap"
    # ライフスタイルのこだわり：ここも金星ベース
    style_key = "style_match" if same_group(your_venus_el, partner_venus_el) else "style_gap"

    money_text = LIFESTYLE_DETAIL_TEXTS.get(money_key, "")
    time_text = LIFESTYLE_DETAIL_TEXTS.get(time_key, "")
    style_detail_text = LIFESTYLE_DETAIL_TEXTS.get(style_key, "")

    # 「支え方・安心感」ブロックのベースになる文章
    emotion_text = money_text or default_emotion_text
    emotion_summary = first_sentence(emotion_text)

    # 「生活リズム・スタイル」の説明（後で care_text にまとめて入る）
    combined_style_text = (time_text + style_detail_text).strip()
    if not combined_style_text:
        combined_style_text = default_style_text
    style_text = combined_style_text
    style_summary = first_sentence(time_text or style_detail_text or default_style_text)

    # ---------- ③ これからの伸ばし方（SUN_VENUS_TEXTS） ----------
    # 太陽×金星のマッチ度合いをざっくり 3 パターンに分類
    def classify_sun_venus() -> str:
        # 両ペアとも同グループ → match
        if same_group(your_sun_el, partner_sun_el) and same_group(your_venus_el, partner_venus_el):
            return "match"
        # 片方だけでも「太陽と金星が同グループ」なら semi_match
        if same_group(your_sun_el, your_venus_el) or same_group(partner_sun_el, partner_venus_el):
            return "semi_match"
        # それ以外は not_match
        return "not_match"

    sun_venus_key = classify_sun_venus()
    future_text_raw = SUN_VENUS_TEXTS.get(sun_venus_key, default_future_text)

    future_text = future_text_raw or default_future_text
    future_summary = first_sentence(future_text)

    return (
        theme_text, theme_summary,
        emotion_text, emotion_summary,
        style_text, style_summary,
        future_text, future_summary,
    )


def build_page7_texts(your_name, partner_name, your_core, partner_core):
    """日常アドバイスページ用テキスト（Page3〜6と同じ思想：文は長めに持っておいて、描画側で行数制御）"""

    # ---------- 共通ヘルパー ----------
    def get_sign(core: dict, key: str) -> str:
        flat = core.get(f"{key}_sign_jp")
        if flat:
            return str(flat)
        v = core.get(key)
        if isinstance(v, dict):
            return (
                v.get("sign_jp")
                or v.get("name_ja")
                or v.get("label")
                or ""
            )
        return str(v) if v is not None else ""

    def sign_to_element(sign_jp: str) -> str:
        if not sign_jp:
            return ""
        s = str(sign_jp)
        if ("牡羊" in s) or ("獅子" in s) or ("射手" in s):
            return "fire"
        if ("牡牛" in s) or ("乙女" in s) or ("山羊" in s):
            return "earth"
        if ("双子" in s) or ("天秤" in s) or ("水瓶" in s):
            return "air"
        if ("蟹" in s) or ("蠍" in s) or ("魚" in s):
            return "water"
        return ""

    def asc_to_group(sign_jp: str) -> str:
        if not sign_jp:
            return "stable"
        s = str(sign_jp)
        if ("牡羊" in s) or ("双子" in s) or ("獅子" in s) or ("天秤" in s) or ("射手" in s) or ("水瓶" in s):
            return "extro"
        if ("牡牛" in s) or ("乙女" in s) or ("山羊" in s):
            return "stable"
        if ("蟹" in s) or ("蠍" in s) or ("魚" in s):
            return "soft"
        return "stable"

    def speed_group(e: str) -> str:
        if e in ("fire", "air"):
            return "fast"
        if e in ("earth", "water"):
            return "slow"
        return ""

    def first_sentence(text: str) -> str:
        parts = split_sentences_jp(text)
        if parts:
            return parts[0]
        return text

    # ---------- 1) 関係テーマ（RELATION_THEME_TEXTS） ----------
    your_sun = get_sign(your_core, "sun")
    partner_sun = get_sign(partner_core, "sun")

    your_sun_el = sign_to_element(your_sun)
    partner_sun_el = sign_to_element(partner_sun)

    if your_sun_el and partner_sun_el and your_sun_el == partner_sun_el:
        rel_el = your_sun_el
    else:
        rel_el = "mixed"

    theme_text = RELATION_THEME_TEXTS.get(rel_el, RELATION_THEME_TEXTS.get("mixed", ""))

    # ---------- 2) 課題ポイント（RELATION_CHALLENGE_TEXTS） ----------
    your_moon_el = sign_to_element(get_sign(your_core, "moon"))
    partner_moon_el = sign_to_element(get_sign(partner_core, "moon"))
    your_venus_el = sign_to_element(get_sign(your_core, "venus"))
    partner_venus_el = sign_to_element(get_sign(partner_core, "venus"))
    your_mars_el = sign_to_element(get_sign(your_core, "mars"))
    partner_mars_el = sign_to_element(get_sign(partner_core, "mars"))
    your_asc_group = asc_to_group(get_sign(your_core, "asc"))
    partner_asc_group = asc_to_group(get_sign(partner_core, "asc"))

    sy = speed_group(your_mars_el)
    sp = speed_group(partner_mars_el)

    if sy and sp and sy != sp:
        challenge_key = "speed_gap"
    elif your_moon_el and partner_moon_el and your_moon_el != partner_moon_el:
        challenge_key = "emotion_gap"
    elif your_venus_el and partner_venus_el and your_venus_el != partner_venus_el:
        challenge_key = "value_gap"
    elif your_asc_group != partner_asc_group:
        challenge_key = "communication_gap"
    else:
        challenge_key = "soft_challenge"

    challenge_text = RELATION_CHALLENGE_TEXTS.get(
        challenge_key,
        RELATION_CHALLENGE_TEXTS.get("soft_challenge", "")
    )

    # ---------- 3) 長く続けるためのキーワード（RELATION_KEYWORD_TEXTS） ----------
    # ここは必ず既存 key のどれかに落とす
    if rel_el == "earth":
        keyword_key = "trust"
    elif rel_el == "air":
        keyword_key = "respect"
    elif rel_el == "fire":
        keyword_key = "balance"
    elif rel_el == "water":
        keyword_key = "emotion"
    else:
        keyword_key = "space"

    keyword_text = (
        RELATION_KEYWORD_TEXTS.get(keyword_key)
        or RELATION_KEYWORD_TEXTS.get("trust", "")
    )

    # ---------- 4) ページ上部 4 行分（ここでは全文を持つ） ----------
    advice_rows = [
        ("ふたりのテーマを感じるとき", theme_text),
        ("すれ違いが起こりやすいとき", challenge_text),
        ("長く続けるためのキーワード",   keyword_text),
        (
            "迷ったり、不安になったとき",
            (
                f"{your_name} さんと {partner_name} さんの関係は、"
                "完璧である必要はありません。"
                "今日できる小さな一歩だけを意識して、"
                "ときどきこのページのテーマとキーワードを思い出してみてください。"
            ),
        ),
    ]

    # ---------- 5) ページ下部のまとめ（短め） ----------
    footer_text = (
    f"{your_name} さんと {partner_name} さんのペアには、"
    f"{first_sentence(theme_text)}"
    f"{first_sentence(keyword_text)}"
    " ふたりが出会ったこと自体が、小さな奇跡のような巡り合わせです。"
    " 完璧さよりも、日々の小さな対話と優しさを重ねていくことが、"
    "迷ったときにも戻ってこられる、安心できる土台になっていきます。"
    " ときどきこのページのテーマとキーワードを思い出しながら、"
    "ふたりだけの物語を、自分たちのペースで育てていってください。"
    )


    return advice_rows, footer_text


def build_page8_texts(your_name, partner_name, your_core, partner_core):
    """
    Page8：まとめ用の短めテキスト。
    - 太陽のエレメントから全体の雰囲気を判断
    - PAGE8_SUMMARY_MAIN だけを使って、1段落のまとめにする
    """

    # --- 太陽星座 → 4元素（fire / earth / air / water）を判定する小ヘルパー ---
    def sign_to_element(sign_jp: str) -> str:
        if not sign_jp:
            return ""
        s = str(sign_jp)
        if ("牡羊" in s) or ("獅子" in s) or ("射手" in s):
            return "fire"
        if ("牡牛" in s) or ("乙女" in s) or ("山羊" in s):
            return "earth"
        if ("双子" in s) or ("天秤" in s) or ("水瓶" in s):
            return "air"
        if ("蟹" in s) or ("蠍" in s) or ("魚" in s):
            return "water"
        return ""

    # --- ふたりの太陽エレメントを取得 ---
    your_sun_el = sign_to_element(your_core.get("sun_sign_jp"))
    partner_sun_el = sign_to_element(partner_core.get("sun_sign_jp"))

    # 同じエレメントならそのまま、それ以外は "mixed"
    if not your_sun_el or not partner_sun_el:
        main_key = "mixed"
    elif your_sun_el == partner_sun_el:
        main_key = your_sun_el
    else:
        main_key = "mixed"

    # --- PAGE8_SUMMARY_MAIN からメインテキストを取得 ---
    base = PAGE8_SUMMARY_MAIN.get(
        main_key,
        (
            "ふたりの関係には、穏やかさと前向きさが同時に流れています。"
            "日々の小さなやり取りや共有が、そのまま絆の強さにつながっていく相性です。"
        ),
    )

    # 辞書の文章は「ふたりの関係には、〜」で始まるので、
    # 名前入りの一文にきれいにつなげる
    if base.startswith("ふたりの関係には、"):
        base_core = base.replace("ふたりの関係には、", "", 1)
        summary = f"{your_name} さんと {partner_name} さんの関係には、{base_core}"
    else:
        summary = f"{your_name} さんと {partner_name} さんの関係には、{base}"

    return summary


# ==============================================================
#                    第 4〜8 页：页面绘制函数
# ==============================================================

# ------------------------------------------------------------------
# Page4：コミュニケーション
# ------------------------------------------------------------------
def draw_page4_communication(
    c,
    talk_text, talk_summary,
    problem_text, problem_summary,
    values_text, values_summary,
):
    # 背景
    draw_full_bg(c, "page_communication.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    # 共通レイアウト設定
    x = 120          # 左余白
    w = 400          # 横幅
    font = JP_SERIF
    size = 12
    lh = 17          # 行間

    # ===== ここで「短/中/長」自動選択（実際は行数に合わせて切る）=====

    # ① 会話の方向性 本文：最大8行想定 → 少し余裕を見て1行24文字くらい
    talk_text_box = trim_text_for_box(talk_text, max_lines=8, chars_per_line=24)

    # ② 暖かいポイント / すれ違いポイント 本文：最大8行
    problem_text_box = trim_text_for_box(problem_text, max_lines=8, chars_per_line=24)

    # ③ 価値観・対話スタイル 本文：最大8行
    values_text_box = trim_text_for_box(values_text, max_lines=8, chars_per_line=24)

    # ===== 実際の描画（本文 max_lines=8 / サマリ max_lines=2）=====

    # ①「会話の方向性」ブロック
    y1 = 640
    y1 = draw_wrapped_block_limited(
        c, talk_text_box, x, y1, w, font, size, lh, max_lines=8
    )
    y1 -= lh
    draw_wrapped_block_limited(
        c, talk_summary, x, y1, w, font, size, lh, max_lines=2
    )

    # ②「暖かいポイント / すれ違いポイント」ブロック
    y2 = 435
    y2 = draw_wrapped_block_limited(
        c, problem_text_box, x, y2, w, font, size, lh, max_lines=8
    )
    y2 -= lh
    draw_wrapped_block_limited(
        c, problem_summary, x, y2, w, font, size, lh, max_lines=2
    )

    # ③「価値観・対話スタイル」ブロック
    y3 = 230
    y3 = draw_wrapped_block_limited(
        c, values_text_box, x, y3, w, font, size, lh, max_lines=8
    )
    y3 -= lh
    draw_wrapped_block_limited(
        c, values_summary, x, y3, w, font, size, lh, max_lines=2
    )

    draw_page_number(c, 4)
    c.showPage()


# ------------------------------------------------------------------
# Page5：良い点・すれ違い・伸ばせる点
# ------------------------------------------------------------------
def draw_page5_points(
    c,
    good_text, good_summary,
    gap_text, gap_summary,
    hint_text, hint_summary,
):
    draw_full_bg(c, "page_points.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    x = 130
    w = 360
    font = JP_SERIF
    size = 12
    lh = 18

    # ===== 行数に合わせて先にテキストを裁断 =====
    # 第5頁は各ブロック：本文 最大6行 ＋ サマリ2行 を想定
    good_text_box = trim_text_for_box(good_text, max_lines=6, chars_per_line=22)
    gap_text_box = trim_text_for_box(gap_text, max_lines=6, chars_per_line=22)
    hint_text_box = trim_text_for_box(hint_text, max_lines=6, chars_per_line=22)

    # ① 良い点ブロック
    y1 = 625
    y1 = draw_wrapped_block_limited(
        c, good_text_box, x, y1, w, font, size, lh, max_lines=6
    )
    y1 -= lh
    draw_wrapped_block_limited(
        c, good_summary, x, y1, w, font, size, lh, max_lines=2
    )

    # ② すれ違いやすい点ブロック
    y2 = 434
    y2 = draw_wrapped_block_limited(
        c, gap_text_box, x, y2, w, font, size, lh, max_lines=6
    )
    y2 -= lh
    draw_wrapped_block_limited(
        c, gap_summary, x, y2, w, font, size, lh, max_lines=2
    )

    # ③ 伸ばせる点ブロック
    y3 = 236
    y3 = draw_wrapped_block_limited(
        c, hint_text_box, x, y3, w, font, size, lh, max_lines=6
    )
    y3 -= lh
    draw_wrapped_block_limited(
        c, hint_summary, x, y3, w, font, size, lh, max_lines=2
    )

    draw_page_number(c, 5)
    c.showPage()



# ------------------------------------------------------------------
# Page6：関係の方向性と今後の傾向
# ------------------------------------------------------------------
def draw_page6_support(
    c,
    type_text, type_summary,      # ① 行動タイプ / エネルギーの方向性
    care_text, care_summary,      # ② 支え方・安心感
    future_text, future_summary,  # ③ これからの伸ばし方・成長ポイント
):
    # 背景
    draw_full_bg(c, "page_trend.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    # 共通レイアウト
    x = 130
    w = 360
    font = JP_SERIF
    size = 12
    lh = 18

    # ===== 先に「箱に収まる長さ」に自動トリムする =====
    # 第6頁も：各ブロック 本文 最大6行（1行あたり22文字くらい目安）
    type_text_box = trim_text_for_box(type_text,   max_lines=6, chars_per_line=22)
    care_text_box = trim_text_for_box(care_text,   max_lines=6, chars_per_line=22)
    future_text_box = trim_text_for_box(future_text, max_lines=6, chars_per_line=22)

    # ===== ① 行動タイプ / エネルギーの方向性 =====
    y1 = 625
    y1 = draw_wrapped_block_limited(
        c, type_text_box, x, y1, w, font, size, lh, max_lines=6
    )
    y1 -= lh
    draw_wrapped_block_limited(
        c, type_summary, x, y1, w, font, size, lh, max_lines=2
    )

    # ===== ② 支え方・安心感 =====
    y2 = 434
    y2 = draw_wrapped_block_limited(
        c, care_text_box, x, y2, w, font, size, lh, max_lines=6
    )
    y2 -= lh
    draw_wrapped_block_limited(
        c, care_summary, x, y2, w, font, size, lh, max_lines=2
    )

    # ===== ③ これからの伸ばし方・成長ポイント =====
    y3 = 236
    y3 = draw_wrapped_block_limited(
        c, future_text_box, x, y3, w, font, size, lh, max_lines=6
    )
    y3 -= lh
    draw_wrapped_block_limited(
        c, future_summary, x, y3, w, font, size, lh, max_lines=2
    )

    draw_page_number(c, 6)
    c.showPage()



# ------------------------------------------------------------------
# Page7：日常アドバイス
# ------------------------------------------------------------------
def draw_page7_advice(c, advice_rows, footer_text):
    draw_full_bg(c, "page_advice.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    table_x = 130
    table_w = 360
    col1_w = 140
    gap = 20
    col2_w = table_w - col1_w - gap

    font = JP_SERIF
    size = 11
    lh = 16

    header_y = 660

    # ---- ヘッダー ----
    c.setFont(JP_SANS, size + 2)
    c.drawString(table_x, header_y, "ふたりのシーン")
    c.drawString(table_x + col1_w + gap, header_y, "うまくいくコツ")

    c.setStrokeColorRGB(0.9, 0.9, 0.9)
    c.setLineWidth(0.4)
    c.line(table_x, header_y - 8, table_x + table_w, header_y - 8)

    # ---- 各ブロック用にあらかじめ裁断 ----
    # 右側の「うまくいくコツ」は 1ブロック 最大6行 × 4ブロック想定
    trimmed_rows = []
    for scene_text, tip_text in advice_rows:
        tip_box = trim_text_for_box(tip_text, max_lines=6, chars_per_line=22)
        trimmed_rows.append((scene_text, tip_box))

    advice_rows = trimmed_rows

    # 一番下のまとめは 最大4行くらいに
    footer_text_box = trim_text_for_box(footer_text, max_lines=6, chars_per_line=30)

    # ---- 本文描画 ----
    y = header_y - lh * 1.8
    c.setFont(font, size)

    for scene_text, tip_text in advice_rows:
        row_top = y

        # 左：シーン名 → 最大2行あれば十分
        sy = draw_wrapped_block_limited(
            c, scene_text, table_x, row_top, col1_w,
            font, size, lh, max_lines=2
        )

        # 右：アドバイス本文 → 最大6行
        ty = draw_wrapped_block_limited(
            c, tip_text, table_x + col1_w + gap, row_top, col2_w,
            font, size, lh, max_lines=6
        )

        bottom = min(sy, ty)
        c.line(table_x, bottom + 4, table_x + table_w, bottom + 4)
        y = bottom - lh

    # ---- 下部まとめ ----
    summary_y = y - lh
    draw_wrapped_block_limited(
        c, footer_text_box, table_x, summary_y, table_w,
        font, size, lh, max_lines=6,
    )

    draw_page_number(c, 7)
    c.showPage()


# ------------------------------------------------------------------
# Page8：まとめ（最後のまとめ文章）
# ------------------------------------------------------------------
def draw_page8_summary(c, summary_text):
    draw_full_bg(c, "page_summary.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    x = 120
    y = 660   # ← 整体稍微往下拉一点
    w = 350
    lh = 20
    size = 13

    # 1ページに収まるようにトリミング
    summary_box = trim_text_for_box(summary_text, max_lines=22, chars_per_line=28)

    draw_wrapped_block_limited(
        c, summary_box, x, y, w,
        JP_SERIF, size, lh,
        max_lines=22,
    )

    draw_page_number(c, 8)
    c.showPage()


# ============================================================
# 出生時間の文字（例: "08:00〜09:00"）を HH:MM に変換する小関数
# ============================================================
def normalize_time_label(v: str) -> str:
    if "不明" in v:
        return "12:00"              # 完全不明 → 正午

    # 例: "08:00〜09:00"
    if "〜" in v:
        left = v.split("〜")[0]      # "08:00"
        hour = int(left.split(":")[0])
        if hour == 24:
            hour = 0
        return f"{hour:02d}:30"      # 区間の真ん中の時間

    return v


# ==============================================================
#                    生成 PDF 主入口
# ==============================================================

@app.route("/api/generate_report", methods=["GET", "POST"])
def generate_report():

    # ---- 1. 读取参数 ----
    your_name = (
        request.args.get("your_name")
        or request.args.get("name")
        or ""
    )

    partner_name = (
        request.args.get("partner_name")
        or request.args.get("partner")
        or ""
    )

    raw_date = request.args.get("date")
    date_display = get_display_date(raw_date)

    your_dob = request.args.get("your_dob") or "1990-01-01"
    raw_your_time = request.args.get("your_time") or "12:00"
    your_time = normalize_time_label(raw_your_time)
    your_place = request.args.get("your_place") or "Tokyo"

    partner_dob = request.args.get("partner_dob") or "1990-01-01"
    raw_partner_time = request.args.get("partner_time") or "12:00"
    partner_time = normalize_time_label(raw_partner_time)
    partner_place = request.args.get("partner_place") or "Tokyo"

    # ---- 2. 计算双方核心星盘 ----
    your_core = compute_core_from_birth(your_dob, your_time, your_place)
    partner_core = compute_core_from_birth(partner_dob, partner_time, partner_place)

    # ---- 3. PDF 缓冲区 ----
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # =======================
    # PAGE 1：封面
    # =======================
    draw_full_bg(c, "cover.jpg")
    c.setFont(JP_SANS, 20)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    couple_text = f"{your_name} さん ＆ {partner_name} さん"
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    c.setFont(JP_SANS, 12)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)
    c.showPage()

    # =======================
    # PAGE 2：イントロ
    # =======================
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # =======================
    # PAGE 3：相性まとめ
    # =======================
    compat_text, sun_text, moon_text, asc_text = build_page3_texts(
        your_name,
        partner_name,
        your_core,
        partner_core,
    )

    draw_page3_basic_and_synastry(
        c,
        your_name,
        partner_name,
        your_core,
        partner_core,
        compat_text,
        sun_text,
        moon_text,
        asc_text,
    )

    # =======================
    # PAGE 4：コミュニケーション
    # =======================
    (
        talk_text, talk_summary,
        problem_text, problem_summary,
        values_text, values_summary,
    ) = build_page4_texts(your_name, partner_name, your_core, partner_core)

    draw_page4_communication(
        c,
        talk_text, talk_summary,
        problem_text, problem_summary,
        values_text, values_summary,
    )

    # =======================
    # PAGE 5：良い点・すれ違い
    # =======================
    (
        good_text, good_summary,
        gap_text, gap_summary,
        hint_text, hint_summary,
    ) = build_page5_texts(your_name, partner_name, your_core, partner_core)

    draw_page5_points(
        c,
        good_text, good_summary,
        gap_text, gap_summary,
        hint_text, hint_summary,
    )

    # ======================
    # PAGE 6：方向性と今後
    # ======================
    (
        theme_text, theme_summary,
        emotion_text, emotion_summary,
        style_text, style_summary,
        future_text, future_summary,
    ) = build_page6_texts(your_name, partner_name, your_core, partner_core)

    # --- 新レイアウト用にマッピング ---
    # ① 行動タイプ / エネルギーの方向性 → 旧：テーマ部分
    type_text = theme_text
    type_summary = theme_summary

    # ② 支え方・安心感 → 旧：感情＋スタイル部分をまとめて本文にする
    care_text = emotion_text + " " + style_text
    care_summary = emotion_summary  # サマリーはまず感情側だけ使う

    # ③ これからの伸ばし方・成長ポイント → 旧：future をそのまま使う

    draw_page6_support(
        c,
        type_text, type_summary,
        care_text, care_summary,
        future_text, future_summary,
    )


    # =======================
    # PAGE 7：アドバイス
    # =======================
    advice_rows, footer_text = build_page7_texts(
        your_name, partner_name, your_core, partner_core
    )

    draw_page7_advice(c, advice_rows, footer_text)

    # =======================
    # PAGE 8：まとめ（動的版）
    # =======================
    summary_text = build_page8_texts(
    your_name, partner_name, your_core, partner_core
    )
    draw_page8_summary(c, summary_text)


    # =======================
    # 完成
    # =======================
    c.save()
    buffer.seek(0)

    filename = f"love_report_{your_name}_{partner_name}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


# ------------------------------------------------------------------
# Tally webhook
# ------------------------------------------------------------------
@app.route("/tally_webhook", methods=["POST"])
def tally_webhook():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    print("Tally webhook payload:", data)
    return {"status": "ok"}


# ------------------------------------------------------------------
# Root & test.html
# ------------------------------------------------------------------
@app.route("/")
def root():
    return "PDF server running."


@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")


# ------------------------------------------------------------------
# 主程序入口
# ------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

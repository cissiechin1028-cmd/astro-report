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

    your_sun = get_sign_name(your_core, "sun")
    partner_sun = get_sign_name(partner_core, "sun")

    compat_text = build_pair_summary_from_sun(your_sun, partner_sun)

    sun_text = (
        f"太陽星座の組み合わせから見ると、"
        f"{your_name}さんと{partner_name}さんは、お互いの個性を通じて成長していけるペアです。"
        "価値観の共通点と違いの両方が、関係のアクセントになっていきます。"
    )

    moon_text = (
        "月は、ふたりが一緒にいるときの「安心感」や素の自分を表します。"
        "感情のペースが少し違っても、丁寧に言葉にして伝えることで、"
        "居心地のよさがぐっと高まっていきます。"
    )

    asc_text = (
        "ASC（第一印象）の相性は、出会ったときのフィーリングや、"
        "外から見たふたりの雰囲気を示します。"
        "少しずつ素の自分を見せ合うことが、長く続く関係のカギになります。"
    )

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

    return {
        "sun": {
            "deg": core["sun"]["lon"],
            "label": fmt("太陽", core["sun"]),
        },
        "moon": {
            "deg": core["moon"]["lon"],
            "label": fmt("月", core["moon"]),
        },
        "venus": {
            "deg": core["venus"]["lon"],
            "label": fmt("金星", core["venus"]),
        },
        "mars": {
            "deg": core["mars"]["lon"],
            "label": fmt("火星", core["mars"]),
        },
        "asc": {
            "deg": core["asc"]["lon"],
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
    draw_full_bg(c, "page_basic.jpg")

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

    c.drawImage(chart_img, left_x, left_y,
                width=chart_size, height=chart_size, mask="auto")
    c.drawImage(chart_img, right_x, right_y,
                width=chart_size, height=chart_size, mask="auto")

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

    c.setFont(JP_SERIF, 14)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(left_cx, left_y - 25, f"{your_name} さん")
    c.drawCentredString(right_cx, right_y - 25, f"{partner_name} さん")

    c.setFont(JP_SERIF, 8.5)
    your_lines = [info["label"] for info in your_planets.values()]
    for i, line in enumerate(your_lines):
        y = left_y - 45 - i * 11
        c.drawString(left_cx - 30, y, line)

    partner_lines = [info["label"] for info in partner_planets.values()]
    for i, line in enumerate(partner_lines):
        y = right_y - 45 - i * 11
        c.drawString(right_cx - 30, y, line)

    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    c.setFont(JP_SANS, 12)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(text_x, 350, "ふたりの相性バランス：")

    draw_wrapped_block_limited(
        c,
        compat_text,
        text_x,
        350 - line_height * 1.4,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=2,
    )

    y_analysis = 220
    c.setFont(body_font, body_size)
    for block_text in (sun_text, moon_text, asc_text):
        y_analysis = draw_wrapped_block_limited(
            c,
            block_text,
            text_x,
            y_analysis,
            wrap_width,
            body_font,
            body_size,
            line_height,
            max_lines=3,
        )
        y_analysis -= line_height

    draw_page_number(c, 3)
    c.showPage()

# ==============================================================
#                    第 4〜8 页：页面绘制函数
# ==============================================================

# ------------------------------------------------------------------
# Page4：コミュニケーション（文章は固定のまま）
# ------------------------------------------------------------------
def draw_page4_communication(
    c,
    talk_text, talk_summary,
    problem_text, problem_summary,
    values_text, values_summary,
):
    draw_full_bg(c, "page_communication.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    x = 130
    w = 360
    font = JP_SERIF
    size = 12
    lh = 18

    y1 = 625
    y1 = draw_wrapped_block(c, talk_text, x, y1, w, font, size, lh)
    y1 -= lh
    draw_wrapped_block_limited(c, talk_summary, x, y1, w, font, size, lh, max_lines=1)

    y2 = 430
    y2 = draw_wrapped_block(c, problem_text, x, y2, w, font, size, lh)
    y2 -= lh
    draw_wrapped_block_limited(c, problem_summary, x, y2, w, font, size, lh, max_lines=1)

    y3 = 235
    y3 = draw_wrapped_block(c, values_text, x, y3, w, font, size, lh)
    y3 -= lh
    draw_wrapped_block_limited(c, values_summary, x, y3, w, font, size, lh, max_lines=1)

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

    y1 = 625
    y1 = draw_wrapped_block(c, good_text, x, y1, w, font, size, lh)
    y1 -= lh
    draw_wrapped_block_limited(c, good_summary, x, y1, w, font, size, lh, max_lines=1)

    y2 = 434
    y2 = draw_wrapped_block(c, gap_text, x, y2, w, font, size, lh)
    y2 -= lh
    draw_wrapped_block_limited(c, gap_summary, x, y2, w, font, size, lh, max_lines=1)

    y3 = 236
    y3 = draw_wrapped_block(c, hint_text, x, y3, w, font, size, lh)
    y3 -= lh
    draw_wrapped_block_limited(c, hint_summary, x, y3, w, font, size, lh, max_lines=1)

    draw_page_number(c, 5)
    c.showPage()


# ------------------------------------------------------------------
# Page6：関係の方向性と今後の傾向
# ------------------------------------------------------------------
def draw_page6_trend(
    c,
    theme_text, theme_summary,
    emotion_text, emotion_summary,
    style_text, style_summary,
    future_text, future_summary,
):
    draw_full_bg(c, "page_trend.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    x = 130
    w = 360
    font = JP_SERIF
    size = 12
    lh = 18

    y1 = 620
    y1 = draw_wrapped_block(c, theme_text, x, y1, w, font, size, lh)
    y1 -= lh
    draw_wrapped_block_limited(c, theme_summary, x, y1, w, font, size, lh, max_lines=1)

    y2 = 460
    y2 = draw_wrapped_block(c, emotion_text, x, y2, w, font, size, lh)
    y2 -= lh
    draw_wrapped_block_limited(c, emotion_summary, x, y2, w, font, size, lh, max_lines=1)

    y3 = 300
    y3 = draw_wrapped_block(c, style_text, x, y3, w, font, size, lh)
    y3 -= lh
    draw_wrapped_block_limited(c, style_summary, x, y3, w, font, size, lh, max_lines=1)

    y4 = 145
    y4 = draw_wrapped_block(c, future_text, x, y4, w, font, size, lh)
    y4 -= lh
    draw_wrapped_block_limited(c, future_summary, x, y4, w, font, size, lh, max_lines=1)

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

    header_y = 680

    c.setFont(JP_SANS, size + 2)
    c.drawString(table_x, header_y, "ふたりのシーン")
    c.drawString(table_x + col1_w + gap, header_y, "うまくいくコツ")

    c.setStrokeColorRGB(0.9, 0.9, 0.9)
    c.setLineWidth(0.4)
    c.line(table_x, header_y - 8, table_x + table_w, header_y - 8)

    y = header_y - lh * 1.8
    c.setFont(font, size)

    for scene_text, tip_text in advice_rows:
        row_top = y
        sy = draw_wrapped_block(c, scene_text, table_x, row_top, col1_w, font, size, lh)
        ty = draw_wrapped_block(c, tip_text, table_x + col1_w + gap, row_top, col2_w, font, size, lh)
        bottom = min(sy, ty)
        c.line(table_x, bottom + 4, table_x + table_w, bottom + 4)
        y = bottom - lh

    summary_y = y - lh
    draw_wrapped_block(c, footer_text, table_x, summary_y, table_w, font, size, lh)

    draw_page_number(c, 7)
    c.showPage()


# ------------------------------------------------------------------
# Page8：まとめ（最後のまとめ文章）
# ------------------------------------------------------------------
def draw_page8_summary(c, summary_text):
    draw_full_bg(c, "page_summary.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    x = 120
    y = 680
    w = 350
    lh = 20
    size = 13

    draw_wrapped_block(c, summary_text, x, y, w, JP_SERIF, size, lh)

    draw_page_number(c, 8)
    c.showPage()

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
    your_time = request.args.get("your_time") or "12:00"
    your_place = request.args.get("your_place") or "Tokyo"

    partner_dob = request.args.get("partner_dob") or "1990-01-01"
    partner_time = request.args.get("partner_time") or "12:00"
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
    your_sun = your_core["sun"]["sign_jp"]
    partner_sun = partner_core["sun"]["sign_jp"]

    compat_text = build_pair_summary_from_sun(your_sun, partner_sun)

    draw_page3_basic_and_synastry(
        c,
        your_name,
        partner_name,
        your_core,
        partner_core,
        compat_text,
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

    # =======================
    # PAGE 6：方向性と今後
    # =======================
    (
        theme_text, theme_summary,
        emotion_text, emotion_summary,
        style_text, style_summary,
        future_text, future_summary,
    ) = build_page6_texts(your_name, partner_name, your_core, partner_core)

    draw_page6_trend(
        c,
        theme_text, theme_summary,
        emotion_text, emotion_summary,
        style_text, style_summary,
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
    # PAGE 8：まとめ
    # =======================
    summary_text = (
        f"{your_name} さんと {partner_name} さんの関係には、"
        "安心感と自然な前進力が同時に流れています。"
        "日々の小さな言葉や共有が、これからの未来をより豊かにしていきます。"
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

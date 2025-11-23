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

# ==== Swiss Ephemeris 设置（必须在使用前执行） ====
import swisseph as swe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EPHE_PATH = os.path.join(BASE_DIR, "ephe")

# 设置 ephe 路径，使 swisseph 能找到 sepl/semo/seas 文件
swe.set_ephe_path(EPHE_PATH)
# ====================================================



# ------ Swiss Ephemeris 尝试导入（不需要 ephe 目录） ------
HAS_SWISSEPH = True



# ------------------------------------------------------------------
# Flask 基本设置：public 目录作为静态目录
# ------------------------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')


# ------------------------------------------------------------------
# 占星符号数组 + lon → 星座函数（必须在 compute 之前）
# ------------------------------------------------------------------
ZODIAC_SIGNS = [
    "牡羊座","牡牛座","双子座","巨蟹座",
    "獅子座","乙女座","天秤座","蠍座",
    "射手座","山羊座","水瓶座","魚座",
]


def lon_to_sign(lon):
    # swisseph.calc_ut 可能整包传进来 → 先拆出第 0 个
    if isinstance(lon, (tuple, list)):
        lon = lon[0]

    lon = float(lon)
    idx = int(lon // 30) % 12
    return ZODIAC_SIGNS[idx]


# ------------------------------------------------------------------
# 计算星座位置（必须在路由之前）
# ------------------------------------------------------------------
def compute_astrology_positions(year, month, day, hour, minute, lat, lon):
    decimal_hour = hour + minute / 60
    jd = swe.julday(year, month, day, decimal_hour)

    sun_lon   = swe.calc_ut(jd, swe.SUN)[0]
    moon_lon  = swe.calc_ut(jd, swe.MOON)[0]
    venus_lon = swe.calc_ut(jd, swe.VENUS)[0]
    mars_lon  = swe.calc_ut(jd, swe.MARS)[0]

    houses, ascmc = swe.houses(jd, lat, lon)
    asc_lon = ascmc[0]

    return {
        "sun": lon_to_sign(sun_lon),
        "moon": lon_to_sign(moon_lon),
        "venus": lon_to_sign(venus_lon),
        "mars": lon_to_sign(mars_lon),
        "asc": lon_to_sign(asc_lon),
    }


# ------------------------------------------------------------------
# 基础目录设置（放在占星逻辑之后）
# ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "public", "assets")
EPHE_DIR = os.path.join(BASE_DIR, "ephe")

# 设置 Swiss Ephemeris 星历路径
if 'HAS_SWISSEPH' in globals() and HAS_SWISSEPH:
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
    theta = math.radians(90 - angle_deg)  # 0° 在上
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
    """
    cx, cy      : 星盘中心
    chart_size  : 整个星盘图片的宽高（正方形）
    angle_deg   : 行星度数（0°=白羊 0°，在 12 点）
    color_rgb   : 小圆点颜色 (r, g, b)
    icon_filename : public/assets 下的 PNG 文件名
    """

    # 根据星盘大小估一个“外圈点的半径”和“内圈图标的半径”
    r_dot = chart_size * 0.34   # 彩色点：接近黄道外圈
    r_icon = chart_size * 0.28  # 图标：更靠内圈，不挡星座符号

    # 彩色小圆点位置（外圈）
    px, py = polar_to_xy(cx, cy, r_dot, angle_deg)
    r, g, b = color_rgb
    c.setFillColorRGB(r, g, b)
    c.circle(px, py, 2.3, fill=1, stroke=0)

    # 图标位置（内圈）
    ix, iy = polar_to_xy(cx, cy, r_icon, angle_deg)

    icon_path = os.path.join(ASSETS_DIR, icon_filename)
    icon_img = ImageReader(icon_path)
    icon_size = 11  # PNG 尺寸

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
    """
    在 (x, y_start) 开始画一段文字，按字符宽度自动换行。
    返回最后一行画完后的下一行 y 坐标（方便接着往下画）。
    """
    c.setFont(font_name, font_size)
    line = ""
    y = y_start

    for ch in text:
        if ch == "\n":
            # 手动换行
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
    """
    在 (x, y_start) 开始画一段文字，自动换行，但最多画 max_lines 行。
    返回最后一行画完后的下一行 y 坐标。
    """
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


# ------------------------------------------------------------------
# 根路径 & test.html
# ------------------------------------------------------------------
@app.route("/")
def root():
    return "PDF server running."


@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")


# ==============================================================
#           第 3〜7 页：页面绘制函数
# ==============================================================

# ------------------------------------------------------------------
# 第 3 页：基本ホロスコープと総合相性
# ------------------------------------------------------------------
def draw_page3_basic_and_synastry(
    c,
    male_name: str,
    female_name: str,
    male_core: dict,
    female_core: dict,
    compat_score: int,
    compat_summary: str,
    sun_text: str,
    moon_text: str,
    asc_text: str,
):
    # 背景
    draw_full_bg(c, "page_basic.jpg")

    # 星盘底图
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

    # 左右两张星盘
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

    # 行星数据块（含度数和文本）
    male_planets = build_planet_block(male_core)
    female_planets = build_planet_block(female_core)

    # 图标文件
    icon_files = {
        "sun": "icon_sun.png",
        "moon": "icon_moon.png",
        "venus": "icon_venus.png",
        "mars": "icon_mars.png",
        "asc": "icon_asc.png",
    }

    # 左右配色
    male_color = (0.15, 0.45, 0.9)
    female_color = (0.9, 0.35, 0.65)

    # 男性盘行星
    for key, info in male_planets.items():
        draw_planet_icon(
            c,
            left_cx,
            left_cy,
            chart_size,
            info["deg"],
            male_color,
            icon_files[key],
        )

    # 女性盘行星
    for key, info in female_planets.items():
        draw_planet_icon(
            c,
            right_cx,
            right_cy,
            chart_size,
            info["deg"],
            female_color,
            icon_files[key],
        )

    # 姓名
    c.setFont(JP_SERIF, 14)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(left_cx, left_y - 25, f"{male_name} さん")
    c.drawCentredString(right_cx, right_y - 25, f"{female_name} さん")

    # 星座标签（太陽・月・金星・火星・ASC）
    c.setFont(JP_SERIF, 8.5)
    male_lines = [info["label"] for info in male_planets.values()]
    for i, line in enumerate(male_lines):
        y = left_y - 45 - i * 11
        c.drawString(left_cx - 30, y, line)

    female_lines = [info["label"] for info in female_planets.values()]
    for i, line in enumerate(female_lines):
        y = right_y - 45 - i * 11
        c.drawString(right_cx - 30, y, line)

    # 中间文字区（相性まとめ + 太陽/月/ASC）
    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    # 相性バランス見出し
    c.setFont(JP_SANS, 12)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(text_x, 350, "ふたりの相性バランス：")

    # 相性まとめ（2行まで）
    draw_wrapped_block_limited(
        c,
        compat_summary,
        text_x,
        350 - line_height * 1.4,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=2,
    )

    # 太陽 / 月 / ASC の説明
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

    # 页码 + 换页
    draw_page_number(c, 3)
    c.showPage()



# ------------------------------------------------------------------
# 第 4 页：性格の違いとコミュニケーション（变量版）
# ------------------------------------------------------------------
def draw_page4_communication(
    c,
    talk_text, talk_summary,
    problem_text, problem_summary,
    values_text, values_summary,
):
    draw_full_bg(c, "page_communication.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    y = 625
    y = draw_wrapped_block(
        c,
        talk_text,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height
    )
    y -= line_height
    draw_wrapped_block_limited(
        c,
        talk_summary,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1
    )

    y2 = 434
    y2 = draw_wrapped_block(
        c,
        problem_text,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height
    )
    y2 -= line_height
    draw_wrapped_block_limited(
        c,
        problem_summary,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1
    )

    y3 = 236
    y3 = draw_wrapped_block(
        c,
        values_text,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height
    )
    y3 -= line_height
    draw_wrapped_block_limited(
        c,
        values_summary,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1
    )

    draw_page_number(c, 4)
    c.showPage()


# ------------------------------------------------------------------
# 第 5 页：相性の良い点・すれ違いやすい点（变量版）
# ------------------------------------------------------------------
def draw_page5_points(
    c,
    good_text, good_summary,
    gap_text, gap_summary,
    hint_text, hint_summary,
):
    draw_full_bg(c, "page_points.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    y = 625
    y = draw_wrapped_block(
        c,
        good_text,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y -= line_height
    draw_wrapped_block_limited(
        c,
        good_summary,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    y2 = 434
    y2 = draw_wrapped_block(
        c,
        gap_text,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y2 -= line_height
    draw_wrapped_block_limited(
        c,
        gap_summary,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    y3 = 236
    y3 = draw_wrapped_block(
        c,
        hint_text,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y3 -= line_height
    draw_wrapped_block_limited(
        c,
        hint_summary,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    draw_page_number(c, 5)
    c.showPage()


# ------------------------------------------------------------------
# 第 6 页：関係の方向性と今後の傾向（变量版）
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

    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    y = 620
    y = draw_wrapped_block(
        c,
        theme_text,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y -= line_height
    draw_wrapped_block_limited(
        c,
        theme_summary,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    y2 = 460
    y2 = draw_wrapped_block(
        c,
        emotion_text,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y2 -= line_height
    draw_wrapped_block_limited(
        c,
        emotion_summary,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    y3 = 300
    y3 = draw_wrapped_block(
        c,
        style_text,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y3 -= line_height
    draw_wrapped_block_limited(
        c,
        style_summary,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    y4 = 145
    y4 = draw_wrapped_block(
        c,
        future_text,
        text_x,
        y4,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y4 -= line_height
    draw_wrapped_block_limited(
        c,
        future_summary,
        text_x,
        y4,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    draw_page_number(c, 6)
    c.showPage()


# ------------------------------------------------------------------
# 第 7 页：日常で役立つアドバイス（变量版）
# ------------------------------------------------------------------
def draw_page7_advice(c, advice_rows, footer_text):
    """
    advice_rows: [(scene_text, tip_text), ...]
    footer_text: 最下方那段 2 行以内的小总结
    """
    draw_full_bg(c, "page_advice.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    table_x = 130
    table_width = 360
    col1_width = 140
    col_gap = 20
    col2_width = table_width - col1_width - col_gap

    body_font = JP_SERIF
    body_size = 11
    line_height = 16

    header_y = 680

    header_font_size = body_size + 2
    c.setFont(JP_SANS, header_font_size)
    c.drawString(table_x, header_y, "ふたりのシーン")
    c.drawString(table_x + col1_width + col_gap, header_y, "うまくいくコツ")

    c.setStrokeColorRGB(0.9, 0.9, 0.9)
    c.setLineWidth(0.4)
    c.line(table_x, header_y - 8, table_x + table_width, header_y - 8)

    y_row = header_y - line_height * 1.8

    c.setFont(body_font, body_size)

    for scene_text, tip_text in advice_rows:
        row_top = y_row

        scene_y = draw_wrapped_block(
            c,
            scene_text,
            table_x,
            row_top,
            col1_width,
            body_font,
            body_size,
            line_height,
        )
        tip_y = draw_wrapped_block(
            c,
            tip_text,
            table_x + col1_width + col_gap,
            row_top,
            col2_width,
            body_font,
            body_size,
            line_height,
        )
        row_bottom = min(scene_y, tip_y)
        c.line(table_x, row_bottom + 4, table_x + table_width, row_bottom + 4)
        y_row = row_bottom - line_height

    summary_y_start = y_row - line_height
    draw_wrapped_block(
        c,
        footer_text,
        table_x,
        summary_y_start,
        table_width,
        body_font,
        body_size,
        line_height,
    )

    draw_page_number(c, 7)
    c.showPage()


# ------------------------------------------------------------------
# 第 8 页：まとめ 用の文面生成（变量版）
# ------------------------------------------------------------------
def build_page8_summary(male_name: str, female_name: str, compat_score: int) -> str:
    return (
        f"{male_name} さんと {female_name} さんのホロスコープからは、"
        "ふたりが出会ったこと自体に、やわらかな意味合いが感じられます。"
        "価値観やペースの違いはありながらも、安心できるところと刺激になるところが、"
        "ちょうどよく混ざり合っている組み合わせです。"
        "大切なのは、どちらか一方の正解に寄せるのではなく、"
        "ふたりだけのちょうどいい距離感や歩幅を、少しずつ探していくことです。"
        "このレポートで気になったポイントがあれば、小さな会話のきっかけとして、"
        "「実はこう感じていたんだ」と伝えてみてください。"
        "星の配置は、完璧なかたちを決めつけるものではなく、"
        "ふたりがこれから選んでいく物語を、そっと照らしてくれるヒントです。"
    )


# ==============================================================
#           星盘核心计算：优先用瑞士星历（真算法）
# ==============================================================

SIGNS_JA = [
    "牡羊座", "牡牛座", "双子座", "蟹座", "獅子座", "乙女座",
    "天秤座", "蠍座", "射手座", "山羊座", "水瓶座", "魚座",
]

def lon_to_sign_name(lon: float) -> str:
    """黄经度数 → 12星座（日文名）"""
    idx = int(lon // 30) % 12
    return SIGNS_JA[idx]


# ----------------------------------------------------
# 简单星座计算（备用）：只用日期+时间，纯假算法
# ----------------------------------------------------
def compute_simple_signs(birth_date, birth_time):
    """
    这是【备用】假算法，只有在没有安装 pyswisseph
    或真算法报错时才会使用。
    """
    try:
        y, m, d = [int(x) for x in birth_date.split("-")]
    except:
        y, m, d = 1990, 1, 1

    try:
        hh, mm = [int(x) for x in birth_time.split(":")]
    except:
        hh, mm = 12, 0

    seed = (y * 1231 + m * 97 + d * 13 + hh * 7 + mm) % 360

    def fake(offset):
        idx = ((seed + offset) % 360) // 30
        return SIGNS_JA[int(idx)]

    return {
        "sun":   fake(0),
        "moon":  fake(40),
        "asc":   fake(80),
        "venus": fake(160),
        "mars":  fake(220),
    }


# ----------------------------------------------------
# 真实星盘：用 Swiss Ephemeris（Moshier 模式，不需要 ephe）
# ----------------------------------------------------
def compute_core_real(birth_date, birth_time, birth_place):
    """
    使用 pyswisseph 计算：
      - 太阳 Sun
      - 月亮 Moon
      - 金星 Venus
      - 火星 Mars
      - 上升 ASC（假定在日本，使用东京经纬度，足够做星座判断）

    ⚠ 不需要 ephe 目录：使用 swe.FLG_MOSEPH（Moshier 算法）。
    """

    # 解析生日
    try:
        y, m, d = [int(x) for x in birth_date.split("-")]
    except Exception:
        y, m, d = 1990, 1, 1

    # 解析时间
    try:
        hh, mm = [int(x) for x in birth_time.split(":")]
    except Exception:
        hh, mm = 12, 0

    hour_local = hh + mm / 60.0

    # 你的服务只面向日本用户 → 统一认为 JST(UTC+9)
    hour_ut = hour_local - 9.0

    # UT 的儒略日
    jd_ut = swe.julday(y, m, d, hour_ut)

    flag = swe.FLG_MOSEPH  # 不用 ephe 目录

    def calc_planet(body):
        lon, lat, dist, lon_speed = swe.calc_ut(jd_ut, body, flag)
        return {
            "lon": lon,
            "name_ja": lon_to_sign_name(lon),
        }

    core = {
        "sun":   calc_planet(swe.SUN),
        "moon":  calc_planet(swe.MOON),
        "venus": calc_planet(swe.VENUS),
        "mars":  calc_planet(swe.MARS),
    }

    # ASC：用东京经纬度做近似（星座判断已经非常接近真实）
    tokyo_lat = 35.6895
    tokyo_lon = 139.6917
    houses, ascmc = swe.houses(jd_ut, tokyo_lat, tokyo_lon)
    asc_lon = ascmc[0]
    core["asc"] = {
        "lon": asc_lon,
        "name_ja": lon_to_sign_name(asc_lon),
    }

    return core


def compute_core_from_birth(dob_str, time_str, place_name):
    """
    使用 Swiss Ephemeris 版本
    太阳/月亮/金星/火星/ASC 全部由 swisseph 计算
    """

    # ---- 1. 解析生日 ----
    try:
        year, month, day = [int(x) for x in dob_str.split("-")]
    except Exception:
        year, month, day = 1990, 1, 1

    # ---- 2. 时间（日本本地时间 → UT）----
    try:
        hh, mm = [int(x) for x in time_str.split(":")]
    except Exception:
        hh, mm = 12, 0

    local_hour = hh + mm / 60.0          # 日本时间
    ut_hour = local_hour - 9.0           # 日本为 UTC+9

    # ---- 3. 经纬度（暂时固定为东京，经纬度不看 place_name）----
    lon = 139.6917
    lat = 35.6895

    # ---- 4. 儒略日（UT）----
    jd = swe.julday(year, month, day, ut_hour)

    # ---- 5. 行星黄经（swisseph）----
    sun_lon   = swe.calc_ut(jd, swe.SUN)[0]
    moon_lon  = swe.calc_ut(jd, swe.MOON)[0]
    venus_lon = swe.calc_ut(jd, swe.VENUS)[0]
    mars_lon  = swe.calc_ut(jd, swe.MARS)[0]

    # ---- 6. ASC（House 计算）----
    houses, ascmc = swe.houses(jd, lat, lon)
    asc_lon = ascmc[0]

    # ---- 7. 组装返回结构：兼容旧代码 + 新字段 ----
    core = {
        "sun": {
            "lon": sun_lon,
            "sign_jp": lon_to_sign(sun_lon),
        },
        "moon": {
            "lon": moon_lon,
            "sign_jp": lon_to_sign(moon_lon),
        },
        "venus": {
            "lon": venus_lon,
            "sign_jp": lon_to_sign(venus_lon),
        },
        "mars": {
            "lon": mars_lon,
            "sign_jp": lon_to_sign(mars_lon),
        },
        "asc": {
            "lon": asc_lon,
            "sign_jp": lon_to_sign(asc_lon),
        },
    }

    # 扁平别名字段（给其它地方用，保留兼容）
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

    return core



# ==============================================================
#                    生成 PDF 主入口
# ==============================================================

@app.route("/api/generate_report", methods=["GET", "POST"])
def generate_report():
    ...

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

    # 内部变量名先保持，用来区分“自己 / 对方”
    male_name = your_name
    female_name = partner_name

    raw_date = request.args.get("date")
    date_display = get_display_date(raw_date)

    your_dob = (
        request.args.get("your_dob")
        or request.args.get("dob")
        or "1990-01-01"
    )
    your_time = (
        request.args.get("your_time")
        or "12:00"
    )
    your_place = (
        request.args.get("your_place")
        or "Tokyo"
    )

    partner_dob = (
        request.args.get("partner_dob")
        or "1990-01-01"
    )
    partner_time = (
        request.args.get("partner_time")
        or "12:00"
    )
    partner_place = (
        request.args.get("partner_place")
        or "Tokyo"
    )


    # ---- 2. 计算双方核心星盘（真实度数近似）----
    male_core = compute_core_from_birth(your_dob, your_time, your_place)
    female_core = compute_core_from_birth(partner_dob, partner_time, partner_place)

    # ---- 3. 准备 PDF 缓冲区 ----
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # PAGE 1：封面
    draw_full_bg(c, "cover.jpg")
    c.setFont(JP_SANS, 20)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    c.setFont(JP_SANS, 12)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)

    c.showPage()

    # PAGE 2：このレポートについて
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # PAGE 3：基本ホロスコープと総合相性
    compat_score, compat_summary, sun_text, moon_text, asc_text = build_page3_texts(
        male_name, female_name, male_core, female_core
    )

    draw_page3_basic_and_synastry(
        c,
        male_name,
        female_name,
        male_core,
        female_core,
        compat_score,
        compat_summary,
        sun_text,
        moon_text,
        asc_text,
    )

    # PAGE 4
    def build_page4_texts(male_name, female_name, male_core, female_core):
        talk_text = (
            f"{male_name} さんは、自分の気持ちを言葉にするまでに少し時間をかける、じっくりタイプです。"
            f"一方で、{female_name} さんは、その場で感じたことをすぐに言葉にする、テンポの速いタイプです。"
            "日常会話では、片方が考えている間にもう一方がどんどん話してしまい、"
            "「ちゃんと聞いてもらえていない」と感じる場面が出やすくなります。"
        )
        talk_summary = (
            "一言でいうと、二人の話し方は「スピードの違いを理解し合うことで心地よくつながれるペア」です。"
        )
        problem_text = (
            f"{male_name} さんは、問題が起きたときにまず全体を整理してから、落ち着いて対処しようとします。"
            f"{female_name} さんは、感情の動きに敏感で、まず気持ちを共有したいタイプです。"
            "同じ出来事でも、片方は「どう解決するか」、もう片方は「どう感じたか」を大事にするため、"
            "タイミングがずれると、すれ違いが生まれやすくなります。"
        )
        problem_summary = (
            "一言でいうと、二人は「解決志向」と「共感志向」が支え合う、心強いバランス型のペアです。"
        )
        values_text = (
            f"{male_name} さんは、安定や責任感を重视する一方で、{female_name} さんは、変化やワクワク感を大切にする傾向があります。"
            "お金の使い方や休日の過ごし方、将来のイメージなど、小さな違いが積み重なると、"
            "「なんでわかってくれないの？」と感じる瞬間が出てくるかもしれません。"
        )
        values_summary = (
            "一言でいうと、二人の価値观は違いを否定するのではなく、「お互いの世界を広げ合うきっかけ」になる組み合わせです。"
        )
        return (
            talk_text, talk_summary,
            problem_text, problem_summary,
            values_text, values_summary,
        )

    (
        talk_text, talk_summary,
        problem_text, problem_summary,
        values_text, values_summary,
    ) = build_page4_texts(male_name, female_name, male_core, female_core)

    draw_page4_communication(
        c,
        talk_text, talk_summary,
        problem_text, problem_summary,
        values_text, values_summary,
    )

    # PAGE 5
    def build_page5_texts(male_name, female_name, male_core, female_core):
        good_text = (
            f"{male_name} さんは、相手の立場を考えながら行動できる、落ち着いた安心感のあるタイプです。"
            f"{female_name} さんは、その場の空気を明るくし、素直な気持ちを伝えられるタイプです。"
            "二人が一緒にいると、「安心感」と「温かさ」が自然と周りにも伝わり、"
            "お互いの長所を引き出し合える関係になりやすい組み合わせです。"
        )
        good_summary = (
            "一言でいうと、二人は「一緒にいるだけで場がやわらぎ、温かさが自然と伝わっていくペア」です。"
        )
        gap_text = (
            f"{male_name} さんは、物事を決めるときに慎重に考えたいタイプで、"
            f"{female_name} さんは、流れや直感を大切にして「とりあえずやってみよう」と思うことが多いかもしれません。"
            "そのため、決断のペースや优先順位がずれると、"
            "「どうしてそんなに急ぐの？」「どうしてそんなに慎重なの？」とお互いに感じやすくなります。"
        )
        gap_summary = (
            "一言でいうと、二人のすれ違いは「慎重さ」と「フットワークの軽さ」の差ですが、そのギャップは视野を広げるヒントにもなります。"
        )
        hint_text = (
            f"{male_name} さんの安定感と、{female_name} さんの柔軟さ・明るさが合わさることで、"
            "二人は「現実的で無理のないチャレンジ」を積み重ねていけるペアです。"
            "お互いの考え方を一度言葉にして共有する習惯ができると、"
            "二人だけのペースや目標が见つかり、将来像もより具体的に描きやすくなります。"
        )
        hint_summary = (
            "一言でいうと、二人の伸ばしていけるポイントは「安心できる土台の上で、新しい一歩を一緒に踏み出せる力」です。"
        )
        return (
            good_text, good_summary,
            gap_text, gap_summary,
            hint_text, hint_summary,
        )

    (
        good_text, good_summary,
        gap_text, gap_summary,
        hint_text, hint_summary,
    ) = build_page5_texts(male_name, female_name, male_core, female_core)

    draw_page5_points(
        c,
        good_text, good_summary,
        gap_text, gap_summary,
        hint_text, hint_summary,
    )

    # PAGE 6
    def build_page6_texts(male_name, female_name, male_core, female_core):
        theme_text = (
            "二人の関係は、「安心感」と「前進力」をバランスよく両立させていくタイプです。"
            "大切にしたい価値观や向かう方向が似ているため、土台が安定しやすく、"
            "意見が分かれる場面でも最終的には同じゴールを选びやすいペアです。"
        )
        theme_summary = (
            "一言でいうと、「同じ方向を见て进める安定感のあるテーマ」です。"
        )
        emotion_text = (
            "感情の深まり方は、最初はゆっくりですが、一度安心できると一気に距離が缩まるスタイルです。"
            "相手の気持ちを丁寧に受け取るほど信頼が积み重なり、"
            "日常の小さな会話から亲密さが育っていきます。"
        )
        emotion_summary = (
            "一言でいうと、「ゆっくり始まり、深くつながる流れ」です。"
        )
        style_text = (
            "このペアは、片方が雰囲気をつくり、もう片方が行動を整えるように、"
            "自然と役割分担が生まれやすい组合せです。"
            "生活のペースと会话のリズムが合いやすく、無理なく居心地の良い関係を形にできます。"
        )
        style_summary = (
            "一言でいうと、「调和しながら一绪に形を作る関係」です。"
        )
        future_text = (
            "今后1〜2年は、安心できる土台の上で少しずつ新しい挑戦を重ねていく時期です。"
            "环境の変化にも协力して向き合うことで、関係の方向性がよりはっきりしていきます。"
        )
        future_summary = (
            "一言でいうと、「安定の中で小さな前進が続く時期」です。"
        )
        return (
            theme_text, theme_summary,
            emotion_text, emotion_summary,
            style_text, style_summary,
            future_text, future_summary,
        )

    (
        theme_text, theme_summary,
        emotion_text, emotion_summary,
        style_text, style_summary,
        future_text, future_summary,
    ) = build_page6_texts(male_name, female_name, male_core, female_core)

    draw_page6_trend(
        c,
        theme_text, theme_summary,
        emotion_text, emotion_summary,
        style_text, style_summary,
        future_text, future_summary,
    )

    # PAGE 7
    def build_page7_texts(male_name, female_name, male_core, female_core):
        advice_rows = [
            (
                "忙しい平日の夜",
                "10分だけ携帯を置いて、お互いに「今日いちばん嬉しかったこと」を一つずつ话してみましょう。"
            ),
            (
                "休みの日のデート前",
                "予定を决定する前に「今日はどんな気分？」と闻くひと言だけで、行き先のすれ违いが减りやすくなります。"
            ),
            (
                "気持ちがすれ违ったとき",
                "どちらが正しいかよりも、「今どう感じた？」を先に听くと、落ち着いて话し直しやすくなります。"
            ),
            (
                "记念日や特別な日",
                "完璧を目指しすぎず、「お互いに一つずつ感謝を伝える」くらいのシンプルさが、ちょうどいいバランスです。"
            ),
            (
                "相手が疲れていそうな日",
                "アドバイスよりも「今日はおつかれさま」と一言ねぎらうだけで、安心感がぐっと高まります。"
            ),
            (
                "なんとなく距離を感じるとき",
                "重い话ではなく、「最近ハマっていること教えて？」など、軽いテーマから会话をつなげてみましょう。"
            ),
        ]
        footer_text = (
            "ここに挙げたのはあくまで一例です。"
            "ふたりらしい言葉やタイミングにアレンジしながら、"
            "日常の中で少しずつ「话すきっかけ」を増やしていってください。"
        )
        return advice_rows, footer_text

    advice_rows, footer_text = build_page7_texts(male_name, female_name, male_core, female_core)

    
    draw_page7_advice(c, advice_rows, footer_text)


    def build_page8_summary(male_name, female_name, compat_score):
        return (
            f"{male_name} さんと {female_name} さんの関係は、"
            f"お互いにとって自然体でいられる安心感と、"
            f"前に進むための力を与えてくれる相性を持っています。\n\n"
            f"総合相性スコア: {compat_score} 点\n"
            "日々の小さな会話や共有が、二人の未来をより豊かにしていきます。"
        )


    # PAGE 8：まとめ
    draw_full_bg(c, "page_summary.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    summary_x = 120
    summary_y = 680
    summary_wrap_width = 350
    summary_font = JP_SERIF
    summary_font_size = 13
    summary_line_height = 20

    summary_text = build_page8_summary(male_name, female_name, compat_score)

    draw_wrapped_block(
        c,
        summary_text,
        summary_x,
        summary_y,
        summary_wrap_width,
        summary_font,
        summary_font_size,
        summary_line_height,
    )

    c.showPage()

    # 收尾
    c.save()
    buffer.seek(0)

    filename = f"love_report_{male_name}_{female_name}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


# ------------------------------------------------------------------
# Tally webhook（示例）：接收表单 JSON
# ------------------------------------------------------------------
@app.route("/tally_webhook", methods=["POST"])
def tally_webhook():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    print("Tally webhook payload:", data)
    return {"status": "ok"}


# ------------------------------------------------------------------
# 主程序入口
# ------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

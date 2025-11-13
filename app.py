from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import stringWidth
import io
import os
import datetime
import math

# ------------------------------------------------------------------
# Flask 基本设置
# ------------------------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "public", "assets")

PAGE_WIDTH, PAGE_HEIGHT = A4

# ------------------------------------------------------------------
# 字体设置：无衬线 + 明朝体
# ------------------------------------------------------------------
JP_FONT_SANS = "HeiseiKakuGo-W5"   # 粗一点的无衬线，用在标题
JP_FONT_SERIF = "HeiseiMin-W3"     # 细一点的明朝体，用在正文

pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT_SANS))
pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT_SERIF))


# ------------------------------------------------------------------
# 工具：铺满整页背景
# ------------------------------------------------------------------
def draw_full_bg(c, filename):
    path = os.path.join(ASSETS_DIR, filename)
    img = ImageReader(path)
    c.drawImage(img, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)


# ------------------------------------------------------------------
# 工具：日期格式化 YYYY-MM-DD → 2025年11月14日
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
# 工具：在星盘上画 彩色小圆点 + PNG 图标
# ------------------------------------------------------------------
def draw_planet_icon(
    c,
    cx,
    cy,
    chart_size,
    angle_deg,
    color_rgb,
    icon_filename,
    ring_ratio=0.47,      # 点所在圆环半径（相对整张星盘）
    icon_offset=6,        # 图标相对圆点的位移
    point_radius=2.3,     # 小圆点大小
    icon_size=9,          # 图标 PNG 显示尺寸
):
    """
    angle_deg : 行星角度（0° 在白羊 0°，位于 12 点方向，逆时针增加）
    """

    # 0° 在 12 点方向 → 把数学坐标调整一下
    theta = math.radians(90 - angle_deg)
    radius = chart_size * ring_ratio

    px = cx + radius * math.cos(theta)
    py = cy + radius * math.sin(theta)

    # 小圆点
    r, g, b = color_rgb
    c.setFillColorRGB(r, g, b)
    c.circle(px, py, point_radius, fill=1, stroke=0)

    # 图标 PNG
    icon_path = os.path.join(ASSETS_DIR, icon_filename)
    icon_img = ImageReader(icon_path)

    ix = px + icon_offset * math.cos(theta)
    iy = py + icon_offset * math.sin(theta)

    c.drawImage(
        icon_img,
        ix - icon_size / 2,
        iy - icon_size / 2,
        width=icon_size,
        height=icon_size,
        mask="auto",
    )


# ------------------------------------------------------------------
# 工具：带自动换行的文本块（明朝体正文用）
# ------------------------------------------------------------------
def draw_wrapped_block(
    c,
    text,
    x,
    y_top,
    max_width,
    font_name,
    font_size,
    leading=None,
):
    """
    在 (x, y_top) 位置开始画一段多行文字：
    - 自动按 max_width 换行（按字符宽度）
    - leading 为行距（不传就用 1.6 倍行高）
    返回：最后一行画完之后的 y 位置，方便接着往下排版
    """
    if leading is None:
        leading = font_size * 1.6

    c.setFont(font_name, font_size)

    lines = []
    line = ""
    for ch in text:
        if ch == "\n":         # 手动换行
            lines.append(line)
            line = ""
            continue
        test = line + ch
        if stringWidth(test, font_name, font_size) <= max_width:
            line = test
        else:
            lines.append(line)
            line = ch
    if line:
        lines.append(line)

    for l in lines:
        c.drawString(x, y_top, l)
        y_top -= leading

    return y_top


# ------------------------------------------------------------------
# 路由
# ------------------------------------------------------------------
@app.route("/")
def root():
    return "PDF server running."


@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")


# ------------------------------------------------------------------
# 生成 PDF 主入口
# ------------------------------------------------------------------
@app.route("/api/generate_report", methods=["GET"])
def generate_report():
    # ---- 1. 读取参数 ----
    male_name = request.args.get("male_name", "太郎")
    female_name = request.args.get("female_name", "花子")
    raw_date = request.args.get("date")
    date_display = get_display_date(raw_date)

    # ---- 2. 准备 PDF ----
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # ==============================================================
    # 1) 封面
    # ==============================================================
    draw_full_bg(c, "cover.jpg")

    c.setFont(JP_FONT_SANS, 18)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    c.setFont(JP_FONT_SANS, 12)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)

    c.showPage()

    # ==============================================================
    # 2) 目录页
    # ==============================================================
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # ==============================================================
    # 3) 基本ホロスコープと総合相性
    # ==============================================================
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘位置
    chart_size = 200
    left_x = 90
    left_y = 520
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    left_cx = left_x + chart_size / 2
    left_cy = left_y + chart_size / 2
    right_cx = right_x + chart_size / 2
    right_cy = right_y + chart_size / 2

    # 背景星盘
    c.drawImage(chart_img, left_x, left_y,
                width=chart_size, height=chart_size, mask="auto")
    c.drawImage(chart_img, right_x, right_y,
                width=chart_size, height=chart_size, mask="auto")

    # 行星角度 + 文本
    male_planets = {
        "sun":   {"deg": 12.3,   "label": "太陽：牡羊座 12.3°",   "icon": "icon_sun.png"},
        "moon":  {"deg": 65.4,   "label": "月：双子座 5.4°",     "icon": "icon_moon.png"},
        "venus": {"deg": 147.8,  "label": "金星：獅子座 17.8°",  "icon": "icon_venus.png"},
        "mars":  {"deg": 183.2,  "label": "火星：天秤座 3.2°",   "icon": "icon_mars.png"},
        "asc":   {"deg": 220.1,  "label": "ASC：山羊座 20.1°",  "icon": "icon_asc.png"},
    }

    female_planets = {
        "sun":   {"deg": 8.5,    "label": "太陽：蟹座 8.5°",      "icon": "icon_sun.png"},
        "moon":  {"deg": 150.0,  "label": "月：乙女座 22.0°",    "icon": "icon_moon.png"},
        "venus": {"deg": 214.6,  "label": "金星：蠍座 14.6°",     "icon": "icon_venus.png"},
        "mars":  {"deg": 262.9,  "label": "火星：水瓶座 2.9°",    "icon": "icon_mars.png"},
        "asc":   {"deg": 288.4,  "label": "ASC：魚座 28.4°",    "icon": "icon_asc.png"},
    }

    male_color = (0.15, 0.45, 0.9)   # 蓝
    female_color = (0.9, 0.35, 0.65) # 粉

    # 男方星盘点
    for info in male_planets.values():
        draw_planet_icon(
            c,
            left_cx,
            left_cy,
            chart_size,
            info["deg"],
            male_color,
            info["icon"],
        )

    # 女方星盘点
    for info in female_planets.values():
        draw_planet_icon(
            c,
            right_cx,
            right_cy,
            chart_size,
            info["deg"],
            female_color,
            info["icon"],
        )

    # 星盘下方姓名
    c.setFont(JP_FONT_SANS, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(left_cx, left_y - 25, f"{male_name} さん")
    c.drawCentredString(right_cx, right_y - 25, f"{female_name} さん")

    # 星盘下方 5 行列表：改成明朝体 + 左对齐 + 字号小一点
    c.setFont(JP_FONT_SERIF, 9.5)

    # 男方列表（左边）
    male_lines = [info["label"] for info in male_planets.values()]
    left_text_x = left_cx - 70   # 左右位置
    left_text_y_start = left_y - 50
    line_height = 12             # 行距

    for i, line in enumerate(male_lines):
        y = left_text_y_start - i * line_height
        c.drawString(left_text_x, y, line)

    # 女方列表（右边，稍微往右一点）
    female_lines = [info["label"] for info in female_planets.values()]
    right_text_x = right_cx - 65
    right_text_y_start = right_y - 50

    for i, line in enumerate(female_lines):
        y = right_text_y_start - i * line_height
        c.drawString(right_text_x, y, line)

    c.showPage()

    # ==============================================================
    # 4) 性格の違いとコミュニケーション
    #    全部明朝体 + 自动换行 + 行距拉开
    # ==============================================================
    draw_full_bg(c, "page_communication.jpg")

    body_font = JP_FONT_SERIF      # 明朝体
    body_size = 9.5                # 比之前小一点
    wrap_width = 360               # 行更长一点，右边不那么空
    text_x = 110                   # 左边对齐基准

    # ---- 話し方とテンポ ----
    block1 = (
        f"{male_name} さんは、自分の気持ちを言葉にするまでに少し時間をかける、じっくりタイプです。"
        f"一方で、{female_name} さんは、その場で感じたことをすぐに言葉にする、テンポの速いタイプです。"
        "日常会話では、片方が考えている間にもう一方がどんどん話してしまい、「ちゃんと聞いてもらえていない」と感じる場面が出やすくなります。\n"
        "一言でいうと、二人の話し方は、スピードの違いを理解し合うことで、より心地よくつながれるペアです。"
    )
    y1 = 515
    y1_end = draw_wrapped_block(c, block1, text_x, y1, wrap_width, body_font, body_size)

    # ---- 問題への向き合い方 ----
    block2 = (
        f"{male_name} さんは、問題が起きたときにまず全体を整理してから、落ち着いて対処しようとします。"
        f"{female_name} さんは、感情の動きに敏感で、まず気持ちを共有したいタイプです。"
        "同じ出来事でも、片方は「どう解決するか」、もう片方は「どう感じたか」を大事にするため、タイミングがずれると、すれ違いが生まれやすくなります。\n"
        "一言でいうと、二人は「解決志向」と「共感志向」がうまくかみ合うと心強いバランス型のペアです。"
    )
    y2_title = y1_end - 40   # 与上一块之间留一点空白
    y2_end = draw_wrapped_block(c, block2, text_x, y2_title, wrap_width, body_font, body_size)

    # ---- 価値観のズレ ----
    block3 = (
        f"{male_name} さんは、安定や責任感を重視する一方で、"
        f"{female_name} さんは、変化やワクワク感を大切にする傾向があります。"
        "お金の使い方や休日の過ごし方、将来のイメージなど、小さな違いが重なると「なんでわかってくれないの？」と感じる瞬間が出てくるかもしれません。\n"
        "一言でいうと、二人の価値観は、違いを否定せずに「お互いの世界を広げ合うきっかけ」にできる組み合わせです。"
    )
    y3_title = y2_end - 40
    _ = draw_wrapped_block(c, block3, text_x, y3_title, wrap_width, body_font, body_size)

    c.showPage()

    # ==============================================================
    # 5) 之后几页先只铺背景
    # ==============================================================
    for bg in [
        "page_points.jpg",
        "page_trend.jpg",
        "page_advice.jpg",
        "page_summary.jpg",
    ]:
        draw_full_bg(c, bg)
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

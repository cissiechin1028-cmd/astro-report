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

# ------------------------------------------------------------------
# Flask 基本设置：public 目录作为静态目录
# ------------------------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "public", "assets")

PAGE_WIDTH, PAGE_HEIGHT = A4

# ------------------------------------------------------------------
# 字体设置：用 ReportLab 自带日文字体
# ------------------------------------------------------------------
JP_FONT = "HeiseiKakuGo-W5"   # 无衬线
pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))

# ------------------------------------------------------------------
# 行星图标文件（你放在 public/assets 里的 1~5.png）
# 1: 太陽, 2: 月, 3: ASC, 4: 火星, 5: 金星
# ------------------------------------------------------------------
PLANET_ICONS = {
    "sun":  "1.png",
    "moon": "2.png",
    "asc":  "3.png",
    "mars": "4.png",
    "venus":"5.png",
}

def load_icon(filename):
    path = os.path.join(ASSETS_DIR, filename)
    return ImageReader(path)

ICON_IMAGES = {k: load_icon(v) for k, v in PLANET_ICONS.items()}

# ------------------------------------------------------------------
# 小工具：铺满整页背景图
# ------------------------------------------------------------------
def draw_full_bg(c, filename):
    path = os.path.join(ASSETS_DIR, filename)
    img = ImageReader(path)
    # 记得加 mask="auto" 才不会出现黑底
    c.drawImage(img, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT, mask="auto")

# ------------------------------------------------------------------
# 小工具：处理日期参数，输出 2025年11月13日 这种格式
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
# 在星盘上画「彩色小圆点 + 旁边的 PNG 图标」
# center_x, center_y: 星盘中心
# radius: 行星所在轨道的半径
# angle_deg: 从 12 点方向逆时针的角度
# color_rgb: (r,g,b)
# planet_key: "sun" / "moon" / "venus" / "mars" / "asc"
# ------------------------------------------------------------------
def draw_planet_marker(c, center_x, center_y, radius, angle_deg,
                       color_rgb, planet_key):
    # 角度 -> 坐标
    rad = math.radians(angle_deg)
    px = center_x + radius * math.cos(rad)
    py = center_y + radius * math.sin(rad)

    # 彩色小圆点
    dot_r = 3
    c.setFillColorRGB(*color_rgb)
    c.circle(px, py, dot_r, stroke=0, fill=1)

    # 旁边的小图标（PNG），略小一点
    icon = ICON_IMAGES.get(planet_key)
    if icon is not None:
        icon_size = 9  # 比点略大一点
        # 图标画在圆点右侧，不叠在星座符号上
        icon_x = px + dot_r + 2
        icon_y = py - icon_size / 2
        c.drawImage(
            icon,
            icon_x,
            icon_y,
            width=icon_size,
            height=icon_size,
            mask="auto"
        )

# ------------------------------------------------------------------
# 演示用的角度 & 文本（之后你接星盘数据时，只要替换这里）
# angle: 在圆上的角度（0° = 白羊 0 度在最上面）
# sign_text/deg_text 用来给下面的列表显示
# ------------------------------------------------------------------
def get_sample_planets():
    male = {
        "sun":   {"angle":  25, "sign_text": "牡羊座", "deg_text": "12.3°"},
        "moon":  {"angle":  85, "sign_text": "双子座", "deg_text": " 5.4°"},
        "venus": {"angle": 160, "sign_text": "獅子座", "deg_text": "17.8°"},
        "mars":  {"angle": 220, "sign_text": "天秤座", "deg_text": " 3.2°"},
        "asc":   {"angle": 290, "sign_text": "山羊座", "deg_text": "20.1°"},
    }
    female = {
        "sun":   {"angle": 185, "sign_text": "蟹座",  "deg_text": " 8.5°"},
        "moon":  {"angle": 240, "sign_text": "乙女座","deg_text": "22.0°"},
        "venus": {"angle": 130, "sign_text": "蠍座",  "deg_text": "14.6°"},
        "mars":  {"angle": 350, "sign_text": "水瓶座","deg_text": " 2.9°"},
        "asc":   {"angle":  45, "sign_text": "魚座",  "deg_text": "28.4°"},
    }
    return male, female

# ------------------------------------------------------------------
# 根路径 & test.html
# ------------------------------------------------------------------
@app.route("/")
def root():
    return "PDF server running."

@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")

# ------------------------------------------------------------------
# 生成 PDF 主入口
# GET /api/generate_report?male_name=太郎&female_name=花子&date=2025-01-01
# ------------------------------------------------------------------
@app.route("/api/generate_report", methods=["GET"])
def generate_report():
    # ---- 1. 读取参数 ----
    male_name = request.args.get("male_name", "太郎")
    female_name = request.args.get("female_name", "花子")
    raw_date = request.args.get("date")  # 期望格式：YYYY-MM-DD
    date_display = get_display_date(raw_date)

    # ---- 2. 准备 PDF 缓冲区 ----
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    font = JP_FONT

    # ------------------------------------------------------------------
    # 封面：cover.jpg
    # ------------------------------------------------------------------
    draw_full_bg(c, "cover.jpg")

    # 姓名：放在金色「恋愛占星レポート」正上方（居中）
    c.setFont(font, 18)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    # 作成日：底部中央
    c.setFont(font, 12)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)

    c.showPage()

    # ------------------------------------------------------------------
    # 第 2 页：目录 / 说明页
    # ------------------------------------------------------------------
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # ------------------------------------------------------------------
    # 第 3 页：基本ホロスコープと総合相性
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘尺寸 + 位置
    chart_size = 180
    left_x = 90
    left_y = 450
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    # 画两个干净的星盘（透明底）
    c.drawImage(chart_img, left_x, left_y,
                width=chart_size, height=chart_size, mask="auto")
    c.drawImage(chart_img, right_x, right_y,
                width=chart_size, height=chart_size, mask="auto")

    # 星盘中心 & 行星轨道半径（用内圈半径，大概抓一个 60）
    male_center_x = left_x + chart_size / 2
    male_center_y = left_y + chart_size / 2
    female_center_x = right_x + chart_size / 2
    female_center_y = right_y + chart_size / 2
    planet_radius = chart_size * 0.30  # 具体你可以再微调

    # 行星角度示例（之后你用真数据替换）
    male_planets, female_planets = get_sample_planets()

    # 男: 蓝色, 女: 粉色
    male_color = (0.20, 0.40, 0.95)
    female_color = (0.90, 0.30, 0.70)

    # 在两个星盘上画行星点 + 旁边图标
    for key, info in male_planets.items():
        draw_planet_marker(
            c,
            male_center_x,
            male_center_y,
            planet_radius,
            info["angle"],
            male_color,
            key
        )

    for key, info in female_planets.items():
        draw_planet_marker(
            c,
            female_center_x,
            female_center_y,
            planet_radius,
            info["angle"],
            female_color,
            key
        )

    # 星盘下方姓名
    c.setFont(font, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(male_center_x, left_y - 25, f"{male_name} さん")
    c.drawCentredString(female_center_x, right_y - 25, f"{female_name} さん")

    # 星盘下方行星列表：字体稍微小 & 细一点（减小字号）
    c.setFont(font, 9)
    c.setFillColorRGB(0, 0, 0)

    # 男性行星列表（左）
    text_left_x = male_center_x - 70
    text_base_y = left_y - 50
    line_h = 11

    lines_male = [
        f"太陽：{male_planets['sun']['sign_text']} {male_planets['sun']['deg_text']}",
        f"月：{male_planets['moon']['sign_text']} {male_planets['moon']['deg_text']}",
        f"金星：{male_planets['venus']['sign_text']} {male_planets['venus']['deg_text']}",
        f"火星：{male_planets['mars']['sign_text']} {male_planets['mars']['deg_text']}",
        f"ASC：{male_planets['asc']['sign_text']} {male_planets['asc']['deg_text']}",
    ]
    y = text_base_y
    for line in lines_male:
        c.drawString(text_left_x, y, line)
        y -= line_h

    # 女性行星列表（右，整体对齐）
    text_right_x = female_center_x - 70
    y = text_base_y
    lines_female = [
        f"太陽：{female_planets['sun']['sign_text']} {female_planets['sun']['deg_text']}",
        f"月：{female_planets['moon']['sign_text']} {female_planets['moon']['deg_text']}",
        f"金星：{female_planets['venus']['sign_text']} {female_planets['venus']['deg_text']}",
        f"火星：{female_planets['mars']['sign_text']} {female_planets['mars']['deg_text']}",
        f"ASC：{female_planets['asc']['sign_text']} {female_planets['asc']['deg_text']}",
    ]
    for line in lines_female:
        c.drawString(text_right_x, y, line)
        y -= line_h

    # 勾选标题不再重复画文字（底图本身就有）
    c.showPage()

    # ------------------------------------------------------------------
    # 后面几页先只铺背景
    # ------------------------------------------------------------------
    for bg in [
        "page_communication.jpg",
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
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

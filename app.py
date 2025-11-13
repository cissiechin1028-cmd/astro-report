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
# 字体设置：只用 ReportLab 自带日文字体
# ------------------------------------------------------------------
JP_FONT = "HeiseiKakuGo-W5"   # 无衬线
pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))


# ------------------------------------------------------------------
# 小工具：铺满整页背景图
# ------------------------------------------------------------------
def draw_full_bg(c, filename):
    """
    将 public/assets/filename 这张图拉伸铺满 A4 页面
    """
    path = os.path.join(ASSETS_DIR, filename)
    img = ImageReader(path)
    c.drawImage(img, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)


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
# 根路径 & test.html
# ------------------------------------------------------------------
@app.route("/")
def root():
    return "PDF server running."


@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")


# ------------------------------------------------------------------
# 在星盘上画「彩色圆点 + 行星图标」
# degree: 0–360，占星角度；白羊 0° 在 12 点方向
# ------------------------------------------------------------------
def draw_planet_on_chart(
    c,
    center_x,
    center_y,
    chart_size,
    degree,
    color_rgb,
    icon_text,
    font_name,
):
    # 点的半径（离中心的距离，不是圆点大小）
    r_point = chart_size * 0.30
    r_label = chart_size * 0.22

    # 0° 在 12 点方向，逆时针增加
    angle_rad = math.radians(90 - degree)

    # 圆点坐标
    x = center_x + r_point * math.cos(angle_rad)
    y = center_y + r_point * math.sin(angle_rad)

    # 画小圆点
    c.setFillColorRGB(*color_rgb)
    c.circle(x, y, 3, fill=1, stroke=0)

    # 图标坐标（略靠内圈）
    lx = center_x + r_label * math.cos(angle_rad)
    ly = center_y + r_label * math.sin(angle_rad) - 3  # 微调竖直位置

    c.setFont(font_name, 9)
    c.setFillColorRGB(*color_rgb)

    # ASC 比较长，稍微缩小一点
    if icon_text == "ASC":
        c.setFont(font_name, 7)
    c.drawCentredString(lx, ly, icon_text)


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
    # 只在指定位置加「太郎 さん ＆ 花子 さん」和「作成日：2025年11月13日」
    # ------------------------------------------------------------------
    draw_full_bg(c, "cover.jpg")

    # 姓名：放在金色「恋愛占星レポート」正上方（居中）
    c.setFont(font, 18)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    # 这个高度是针对封面图片微调过的，如果要再动可以再调一点
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    # 作成日：底部中央
    c.setFont(font, 12)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)

    c.showPage()

    # ------------------------------------------------------------------
    # 第 2 页：目录 / 说明页，直接用 index.jpg（不加文字）
    # ------------------------------------------------------------------
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # ------------------------------------------------------------------
    # 第 3 页：基本ホロスコープと総合相性 + 两个星盘
    # 背景：page_basic.jpg
    # 星盘：chart_base.png 一左一右，下方分别写姓名和行星列表
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘尺寸 + 位置
    chart_size = 220
    left_x = 80
    left_y = 520
    right_x = PAGE_WIDTH - chart_size - 80
    right_y = left_y

    # 画两张星盘底图
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

    # 星盘中心
    left_cx = left_x + chart_size / 2
    left_cy = left_y + chart_size / 2
    right_cx = right_x + chart_size / 2
    right_cy = right_y + chart_size / 2

    # 男/女两种颜色
    male_color = (0.15, 0.35, 0.85)   # 蓝
    female_color = (0.88, 0.30, 0.60) # 粉

    # -------------------------------
    # ▼ 示例占星角度（0–360）：以后可换成真实数据
    #   这里只是为了排版和测试
    # -------------------------------
    male_planets = [
        {"icon": "☉", "deg": 12.3},   # 太陽
        {"icon": "☽", "deg": 65.4},   # 月
        {"icon": "♀", "deg": 140.0},  # 金星
        {"icon": "♂", "deg": 220.0},  # 火星
        {"icon": "ASC", "deg": 300.0}, # 上升
    ]

    female_planets = [
        {"icon": "☉", "deg": 8.5},
        {"icon": "☽", "deg": 172.0},
        {"icon": "♀", "deg": 214.6},
        {"icon": "♂", "deg": 250.0},
        {"icon": "ASC", "deg": 328.4},
    ]

    # 在星盘上画「彩色圆点 + 图标」
    for p in male_planets:
        draw_planet_on_chart(
            c,
            left_cx,
            left_cy,
            chart_size,
            p["deg"],
            male_color,
            p["icon"],
            font,
        )

    for p in female_planets:
        draw_planet_on_chart(
            c,
            right_cx,
            right_cy,
            chart_size,
            p["deg"],
            female_color,
            p["icon"],
            font,
        )

    # -------------------------------
    # 星盘下面的行星列表（示例文本）
    # 太阳 / 月 / 金星 / 火星 / 上昇：星座 + 度数
    # -------------------------------
    male_lines = [
        "☉ 太陽：牡羊座 12.3°",
        "☽ 月：双子座 5.4°",
        "♀ 金星：獅子座 17.8°",
        "♂ 火星：天秤座 3.2°",
        "ASC 上昇：山羊座 20.1°",
    ]

    female_lines = [
        "☉ 太陽：蟹座 8.5°",
        "☽ 月：乙女座 22.0°",
        "♀ 金星：蠍座 14.6°",
        "♂ 火星：水瓶座 2.9°",
        "ASC 上昇：魚座 28.4°",
    ]

    # 列表整体的起始 Y（在星盘底部与姓名之间）
    list_start_y = left_y - 20
    line_h = 11

    c.setFont(font, 10)
    c.setFillColorRGB(0.15, 0.15, 0.15)

    # 左边（男）行星列表：以星盘中心为轴居中
    for i, text in enumerate(male_lines):
        y = list_start_y - i * line_h
        c.drawCentredString(left_cx, y, text)

    # 右边（女）行星列表：同样居中
    for i, text in enumerate(female_lines):
        y = list_start_y - i * line_h
        c.drawCentredString(right_cx, y, text)

    # 姓名排在列表下面
    name_y = list_start_y - len(male_lines) * line_h - 12
    c.setFont(font, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(left_cx, name_y, f"{male_name} さん")
    c.drawCentredString(right_cx, name_y, f"{female_name} さん")

    # 注意：不再额外绘制「総合相性スコア」「太陽・月・上昇の分析」标题，
    # 这两个已经在背景图里了。
    c.showPage()

    # ------------------------------------------------------------------
    # 第 4~? 页：先只铺背景图（模板），文字逻辑之后再加
    # 顺序：page_communication -> page_points -> page_trend
    #      -> page_advice -> page_summary
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

    # ------------------------------------------------------------------
    # 收尾 & 返回 PDF
    # ------------------------------------------------------------------
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
    # 本地跑可以用 10000，Render 上会用自己的 PORT 环境变量
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

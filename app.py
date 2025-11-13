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
# 字体设置：只用 ReportLab 自带日文字体，彻底不用外部 TTF/OTF
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
# 星盘绘制小工具（图标 + 内圈标签）
# ------------------------------------------------------------------
def draw_natal_chart(c, center_x, center_y, size, color_rgb, planet_data):
    """
    在给定中心点画一张「chart_base.png」上叠加的本命盘标记。

    - center_x, center_y : 星盘中心
    - size               : 整个盘的直径（和 chart_base.png 保持一致）
    - color_rgb          : (r, g, b) 0~1，男=蓝 女=粉
    - planet_data        : [
          {"label": "太陽", "symbol": "☉", "sign": "牡羊座", "degree": "12.3°", "angle": 10},
          ...
      ]
      angle 只是用来在圆周上排布位置（度数），目前是假数据。
    """
    c.setFillColorRGB(*color_rgb)
    c.setStrokeColorRGB(*color_rgb)

    # 小圆点半径（比之前更小）
    dot_r = 3

    # 行星标记半径：放在内圈，不遮挡外圈黄道符号
    # size / 2 是盘的半径，往里缩一点
    r_dot = size * 0.30          # 圆点半径位置
    r_label = size * 0.22        # 文字再往里一点

    # 行星文字（内圈标签）
    c.setFont(JP_FONT, 8)        # 字体稍微小一点、细一点

    for planet in planet_data:
        angle_deg = planet["angle"]
        symbol = planet["symbol"]

        # 角度：0 度在 3 点钟方向，逆时针
        rad = math.radians(angle_deg)

        # 圆点坐标
        x_dot = center_x + r_dot * math.cos(rad)
        y_dot = center_y + r_dot * math.sin(rad)

        # 文字坐标：从圆点再往中心方向偏移一点
        x_label = center_x + r_label * math.cos(rad)
        y_label = center_y + r_label * math.sin(rad)

        # 画圆点
        c.circle(x_dot, y_dot, dot_r, fill=1, stroke=0)

        # 画符号（☉ ☽ ♀ ♂ / ASC）
        # ASC 是字母，会稍微宽一点，这里统一用 drawCentredString
        c.drawCentredString(x_label, y_label - 3, symbol)  # -3 是为了让文字更居中


def draw_planet_table(c, left_x, top_y, line_height, planet_data):
    """
    在星盘下方画一段「太陽：牡羊座 12.3°」这样的列表。
    left_x : 左边起点 X
    top_y  : 第一行 Y
    """
    c.setFont(JP_FONT, 9)
    c.setFillColorRGB(0, 0, 0)

    for i, planet in enumerate(planet_data):
        text = f"{planet['label']}：{planet['sign']} {planet['degree']}"
        y = top_y - i * line_height
        c.drawString(left_x, y, text)


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

    # 统一字体
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
    # 这个高度你刚才确认过比较合适，如果要再上/下改下面的 420 即可
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    # 作成日：底部中央
    c.setFont(font, 12)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)

    c.showPage()

    # ------------------------------------------------------------------
    # 第 2 页：目录 / 说明页，直接用 index.jpg
    # ------------------------------------------------------------------
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # ------------------------------------------------------------------
    # 第 3 页：基本ホロスコープと総合相性 + 两个星盘
    # 背景：page_basic.jpg
    # 星盘：chart_base.png 一左一右，下方分别写姓名 + 行星度数表
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘尺寸 + 位置
    chart_size = 180         # 直径，和背景图上视觉差不多
    left_x = 90              # 左边星盘左上角 X
    left_y = 510             # 左边星盘左上角 Y（整体向上）
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    # 画底图星盘（不带行星）
    c.drawImage(chart_img, left_x, left_y,
                width=chart_size, height=chart_size, mask="auto")
    c.drawImage(chart_img, right_x, right_y,
                width=chart_size, height=chart_size, mask="auto")

    # 男 / 女 颜色
    male_color = (0.20, 0.40, 0.85)   # 蓝
    female_color = (0.90, 0.35, 0.65) # 粉

    # ====== 假数据：之后接入真实计算时，只要替换这两块 ======
    male_planets = [
        {"label": "太陽", "symbol": "☉", "sign": "牡羊座", "degree": "12.3°", "angle": 10},
        {"label": "月",   "symbol": "☽", "sign": "双子座", "degree": "5.4°",  "angle": 80},
        {"label": "金星", "symbol": "♀", "sign": "獅子座", "degree": "17.8°", "angle": 150},
        {"label": "火星", "symbol": "♂", "sign": "天秤座", "degree": "3.2°",  "angle": 230},
        {"label": "上昇", "symbol": "ASC", "sign": "山羊座", "degree": "20.1°", "angle": 310},
    ]

    female_planets = [
        {"label": "太陽", "symbol": "☉", "sign": "蟹座",   "degree": "8.5°",  "angle": 40},
        {"label": "月",   "symbol": "☽", "sign": "乙女座", "degree": "22.0°", "angle": 120},
        {"label": "金星", "symbol": "♀", "sign": "蠍座",   "degree": "14.6°", "angle": 190},
        {"label": "火星", "symbol": "♂", "sign": "水瓶座", "degree": "2.9°",  "angle": 260},
        {"label": "上昇", "symbol": "ASC", "sign": "魚座", "degree": "28.4°", "angle": 330},
    ]
    # =========================================================

    # 计算星盘中心坐标
    left_center_x = left_x + chart_size / 2
    left_center_y = left_y + chart_size / 2
    right_center_x = right_x + chart_size / 2
    right_center_y = right_y + chart_size / 2

    # 在盘内画行星标记
    draw_natal_chart(c, left_center_x, left_center_y, chart_size, male_color, male_planets)
    draw_natal_chart(c, right_center_x, right_center_y, chart_size, female_color, female_planets)

    # 星盘下方：行星表（姓名上方）
    line_h = 11

    # 左侧表格左边起点（略微向左，让一行能写下）
    left_table_x = left_x - 5
    left_table_top_y = left_y - 10
    draw_planet_table(c, left_table_x, left_table_top_y, line_h, male_planets)

    right_table_x = right_x - 5
    right_table_top_y = right_y - 10
    draw_planet_table(c, right_table_x, right_table_top_y, line_h, female_planets)

    # 星盘下方姓名（再往下放一点，让出给行星表）
    c.setFont(font, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(left_center_x, left_y - 80, f"{male_name} さん")
    c.drawCentredString(right_center_x, right_y - 80, f"{female_name} さん")

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
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    # 本地跑可以用 10000，Render 上会用自己的 PORT 环境变量
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

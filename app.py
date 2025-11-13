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
# 字体：用 ReportLab 自带日文字体
# ------------------------------------------------------------------
JP_FONT = "HeiseiKakuGo-W5"
pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))


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
    icon_size = 11  # PNG 尺寸（可以微调）

    c.drawImage(
        icon_img,
        ix - icon_size / 2,
        iy - icon_size / 2,
        width=icon_size,
        height=icon_size,
        mask="auto",
    )


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
# ------------------------------------------------------------------
@app.route("/api/generate_report", methods=["GET"])
def generate_report():
    # ---- 1. 读取参数 ----
    male_name = request.args.get("male_name", "太郎")
    female_name = request.args.get("female_name", "花子")
    raw_date = request.args.get("date")
    date_display = get_display_date(raw_date)

    # ---- 2. 准备 PDF 缓冲区 ----
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    font = JP_FONT

    # ------------------------------------------------------------------
    # 封面：cover.jpg
    # ------------------------------------------------------------------
    draw_full_bg(c, "cover.jpg")

    # 姓名：恋愛占星レポート 正上方
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
    # 第 2 页：目录页（index.jpg）
    # ------------------------------------------------------------------
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # ------------------------------------------------------------------
    # 第 3 页：基本ホロスコープと総合相性
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘尺寸 + 位置（你现在用的那一版）
    chart_size = 200
    left_x = 90
    left_y = 520
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    # 星盘中心
    left_cx = left_x + chart_size / 2
    left_cy = left_y + chart_size / 2
    right_cx = right_x + chart_size / 2
    right_cy = right_y + chart_size / 2

    # 画星盘底图
    c.drawImage(chart_img, left_x, left_y,
                width=chart_size, height=chart_size, mask="auto")
    c.drawImage(chart_img, right_x, right_y,
                width=chart_size, height=chart_size, mask="auto")

    # ------------------ 行星示例数据（角度 + 文字） ------------------
    # 之后你可以把这些角度和文字换成真实计算结果，只要 key 不变
    male_planets = {
        "sun":   {"deg": 12.3,  "label": "太陽：牡羊座 12.3°"},
        "moon":  {"deg": 65.4,  "label": "月：双子座 5.4°"},
        "venus": {"deg": 147.8, "label": "金星：獅子座 17.8°"},
        "mars":  {"deg": 183.2, "label": "火星：天秤座 3.2°"},
        "asc":   {"deg": 220.1, "label": "ASC：山羊座 20.1°"},
    }

    female_planets = {
        "sun":   {"deg": 8.5,   "label": "太陽：蟹座 8.5°"},
        "moon":  {"deg": 150.0, "label": "月：乙女座 22.0°"},
        "venus": {"deg": 214.6, "label": "金星：蠍座 14.6°"},
        "mars":  {"deg": 262.9, "label": "火星：水瓶座 2.9°"},
        "asc":   {"deg": 288.4, "label": "ASC：魚座 28.4°"},
    }

    # 与 key 对应的 PNG 文件名
    icon_files = {
        "sun": "icon_sun.png",
        "moon": "icon_moon.png",
        "venus": "icon_venus.png",
        "mars": "icon_mars.png",
        "asc": "icon_asc.png",
    }

    # 男 = 蓝色 / 女 = 粉色
    male_color = (0.15, 0.45, 0.9)
    female_color = (0.9, 0.35, 0.65)

    # ------------------ 在星盘上画点 + 图标（内圈） ------------------
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

    # ------------------ 星盘下方姓名 ------------------
    c.setFont(font, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(left_cx, left_y - 25, f"{male_name} さん")
    c.drawCentredString(right_cx, right_y - 25, f"{female_name} さん")

    # ------------------ 星盘下方 5 行列表（细一点、往上挪） ------------------
    c.setFont(font, 8)
    c.setFillColorRGB(0, 0, 0)

    # 男方列表
    male_lines = [info["label"] for info in male_planets.values()]
    for i, line in enumerate(male_lines):
        y = left_y - 45 - i * 11   # 比之前上移一些
        c.drawString(left_cx - 30, y, line)

    # 女方列表
    female_lines = [info["label"] for info in female_planets.values()]
    for i, line in enumerate(female_lines):
        y = right_y - 45 - i * 11
        c.drawString(right_cx - 30, y, line)

    # 不再额外画「総合相性スコア」「太陽・月・上昇の分析」标题
    c.showPage()

        # ------------------------------------------------------------------
    # 第 4 页：性格の違いとコミュニケーション
    # 背景：page_communication.jpg
    # 只在 3 个小标题下方填充正文：
    #  話し方とテンポ
    #  問題への向き合い方
    #  価値観のズレ
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_communication.jpg")

    # 先准备三段文字（目前是模板，之后可以换成占星 AI 生成的内容）
    text_tempo = (
        f"{male_name} さんは、自分の気持ちを言葉にするまでに少し時間をかける、"
        "じっくりタイプ。一方で、"
        f"{female_name} さんは、その場で感じたことをすぐに言葉にする、テンポの速いタイプです。\n"
        "日常会話では、片方が考えている間にもう一方がどんどん話してしまい、"
        "「ちゃんと聞いてもらえていない」と感じる場面が出やすくなります。\n"
        "一言でいうと、二人の話し方は『スピードの違いを理解し合うと心地よくなるペア』です。"
    )

    text_problem = (
        f"{male_name} さんは、問題が起きたときにまず全体を整理してから、"
        "落ち着いて対処しようとする傾向があります。"
        f"{female_name} さんは、感情の動きに敏感で、まず気持ちを共有したいタイプです。\n"
        "同じ出来事でも、片方は「どう解決するか」を先に考え、"
        "もう片方は「どう感じたか」を大事にするため、すれ違いが生まれやすくなります。\n"
        "一言でいうと、二人は『解決志向 と 共感志向』が補い合うバランス型のペアです。"
    )

    text_values = (
        f"{male_name} さんは、安定や責任感を重視する一方で、"
        f"{female_name} さんは、変化やワクワク感を大切にする傾向があります。\n"
        "お金の使い方、休日の過ごし方、将来のイメージなど、"
        "小さな違いが重なって「なんでわかってくれないの？」と感じる瞬間が出てきます。\n"
        "一言でいうと、二人の価値観は『違いを楽しむことで世界が広がる組み合わせ』です。"
    )

    # 简单的“多行文字绘制”小工具（按 \n 换行）
    def draw_paragraph(c, x, y, text, leading=13):
        c.setFont(font, 10)          # 字号 10，看起来比较细
        c.setFillColorRGB(0, 0, 0)
        txt = c.beginText()
        txt.setTextOrigin(x, y)
        txt.setLeading(leading)
        for line in text.split("\n"):
            txt.textLine(line)
        c.drawText(txt)

    # 下面三个坐标需要根据你底图上的标题位置微调
    # 话し方とテンポ 下面的正文
    draw_paragraph(c, 95, 520, text_tempo)

    # 問題への向き合い方 下面的正文
    draw_paragraph(c, 95, 360, text_problem)

    # 価値観のズレ 下面的正文
    draw_paragraph(c, 95, 200, text_values)

    c.showPage()

    # ------------------------------------------------------------------
    # 后面几页只铺背景（占位）
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
    # 收尾
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
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

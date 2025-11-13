from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import io
import os
import datetime

# --------------------------------------------------
# Flask 基本设置：public 目录作为静态目录
# --------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "public", "assets")

PAGE_WIDTH, PAGE_HEIGHT = A4

# --------------------------------------------------
# 字体设置：只用 ReportLab 自带日文字体
# --------------------------------------------------
JP_FONT = "HeiseiKakuGo-W5"  # 无衬线
pdfmetrics.registerFont(UnicodeCIDFont(JP_FONT))


# --------------------------------------------------
# 小工具：铺满整页背景图
# --------------------------------------------------
def draw_full_bg(c, filename: str):
    """将 public/assets/filename 这张图拉伸铺满 A4 页面"""
    path = os.path.join(ASSETS_DIR, filename)
    img = ImageReader(path)
    c.drawImage(img, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)


# --------------------------------------------------
# 小工具：处理日期参数，输出 2025年11月13日 这种格式
# --------------------------------------------------
def get_display_date(raw_date: str | None) -> str:
    if raw_date:
        try:
            d = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            d = datetime.date.today()
    else:
        d = datetime.date.today()

    return f"{d.year}年{d.month}月{d.day}日"


# --------------------------------------------------
# 根路径 & test.html
# --------------------------------------------------
@app.route("/")
def root():
    return "PDF server running."


@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")


# --------------------------------------------------
# 生成 PDF 主入口
#   GET /api/generate_report?male_name=太郎&female_name=花子&date=2025-01-01
# --------------------------------------------------
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

    # --------------------------------------------------
    # 第 1 页：封面 cover.jpg
    # 只加「太郎 さん ＆ 花子 さん」和「作成日：2025年11月13日」
    # --------------------------------------------------
    draw_full_bg(c, "cover.jpg")

    # 姓名：放在金色「恋愛占星レポート」正上方（居中）
    c.setFont(font, 18)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    # 这个 Y 值是针对当前封面的微调位置
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    # 作成日：底部中央
    c.setFont(font, 12)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)

    c.showPage()

    # --------------------------------------------------
    # 第 2 页：说明 & 目录 index.jpg（不加任何额外文字）
    # --------------------------------------------------
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # --------------------------------------------------
    # 第 3 页：基本ホロスコープと総合相性
    #   背景：page_basic.jpg
    #   星盘：chart_base.png 一左一右 + 行星点位 + 姓名 + 两行说明文字
    # --------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘尺寸 + 位置
    chart_size = 180             # 星盘直径
    left_x = 90                  # 左侧星盘左上角 X
    left_y = 520                 # 左右共享 Y（上方空白区域）
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    # 画两个星盘
    c.drawImage(
        chart_img, left_x, left_y,
        width=chart_size, height=chart_size, mask="auto"
    )
    c.drawImage(
        chart_img, right_x, right_y,
        width=chart_size, height=chart_size, mask="auto"
    )

    # ---------- 行星点位 & 标签：全部放在内圈 ----------
    dot_r = 3.5  # 点再小一点

    def draw_dot_text(cx, cy, r, text, color=(0.2, 0.2, 0.8)):
        # 小圆点
        c.setFillColorRGB(*color)
        c.circle(cx, cy, r, fill=1, stroke=0)
        # 标签文字
        c.setFillColorRGB(color[0], color[1], color[2])
        c.setFont(font, 9)
        c.drawString(cx + 5, cy - 3, text)

    # 男性星盘中心
    male_cx = left_x + chart_size / 2
    male_cy = left_y + chart_size / 2

    # (dx, dy) 为相对中心的偏移量 —— 手动调到内圈，不遮挡外圈星座
    male_offsets = [
        (-22,  26, "太陽"),   # 左上
        ( 18,  24, "月"),     # 右上
        (-26,  -6, "火星"),   # 左下
        ( 22,  -4, "金星"),   # 右下
        (  0, -26, "ASC"),    # 正下
    ]

    for dx, dy, label in male_offsets:
        px = male_cx + dx
        py = male_cy + dy
        draw_dot_text(px, py, dot_r, label, color=(0.18, 0.30, 0.80))

    # 女性星盘中心
    female_cx = right_x + chart_size / 2
    female_cy = right_y + chart_size / 2

    female_offsets = [
        (-20,  26, "太陽"),
        ( 18,  24, "月"),
        (-24,  -6, "火星"),
        ( 22,  -4, "金星"),
        (  0, -26, "ASC"),
    ]

    for dx, dy, label in female_offsets:
        px = female_cx + dx
        py = female_cy + dy
        draw_dot_text(px, py, dot_r, label, color=(0.85, 0.20, 0.45))

    # 姓名（星盘下）
    c.setFont(font, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(left_x + chart_size / 2, left_y - 22, f"{male_name} さん")
    c.drawCentredString(right_x + chart_size / 2, right_y - 22, f"{female_name} さん")

    # 两行说明文字（打勾）
    c.setFont(font, 13)
    c.setFillColorRGB(0, 0, 0)
    check = "☑ "
    c.drawString(80, 450, check + "総合相性スコア")
    c.drawString(80, 400, check + "太陽・月・上昇の分析")

    c.showPage()

    # --------------------------------------------------
    # 第 4 〜 8 页：先只铺背景，后面再加文字逻辑
    #   page_communication / page_points / page_trend
    #   page_advice / page_summary
    # --------------------------------------------------
    for bg in [
        "page_communication.jpg",
        "page_points.jpg",
        "page_trend.jpg",
        "page_advice.jpg",
        "page_summary.jpg",
    ]:
        draw_full_bg(c, bg)
        c.showPage()

    # --------------------------------------------------
    # 收尾 & 返回 PDF
    # --------------------------------------------------
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
    # 本地跑：默认 10000；Render 上会传 PORT 环境变量
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import io
import os
import datetime

# ------------------------------------------------------------------
# Flask 基本设置：public 目录作为静态目录
# ------------------------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "public", "assets")

PAGE_WIDTH, PAGE_HEIGHT = A4

# ------------------------------------------------------------------
# 字体设置：只用 ReportLab 自带日文字体，彻底不用 Noto 文件
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
    c.setFillColorRGB(0, 0, 0)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    # 390 这个高度是针对你这张封面的视觉位置微调过的，如果要再上/下可以再改一点点
    c.drawCentredString(PAGE_WIDTH / 2, 480, couple_text)

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
    # 星盘：chart_base.png 一左一右，下方分别写姓名
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘尺寸 + 位置（按你刚才的截图重新调过）
    chart_size = 180         # 直径 200pt，避免撑满
    left_x = 90              # 左边星盘的左上角 X
    left_y = 350             # 左右共同的 Y（整体上移）
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    # 画两个星盘
    c.drawImage(chart_img, left_x, left_y,
                width=chart_size, height=chart_size, mask="auto")
    c.drawImage(chart_img, right_x, right_y,
                width=chart_size, height=chart_size, mask="auto")

    # 星盘下方姓名
    c.setFont(font, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(left_x + chart_size / 2, left_y - 25, f"{male_name} さん")
    c.drawCentredString(right_x + chart_size / 2, right_y - 25, f"{female_name} さん")

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

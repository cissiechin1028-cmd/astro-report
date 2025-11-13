from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

import io
import os
from datetime import datetime

# ---------------------------------------------------------
# Flask 设置：public 目录当静态目录用
# ---------------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')

# ---------------------------------------------------------
# 字体设置：全部用 ReportLab 自带日文字体（不会再报错）
# HeiseiMin-W3   = 明朝系
# HeiseiKakuGo-W5 = ゴシック系
# ---------------------------------------------------------
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))

TITLE_FONT = "HeiseiKakuGo-W5"  # 主标题、名字
BODY_FONT = "HeiseiMin-W3"      # 正文

PAGE_WIDTH, PAGE_HEIGHT = A4


# ---------------------------------------------------------
# 小工具：画整页背景图（cover.jpg 等）
# ---------------------------------------------------------
def draw_full_bg(c: canvas.Canvas, filename: str):
    path = os.path.join(app.static_folder, "assets", filename)
    img = ImageReader(path)
    c.drawImage(img, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)


# ---------------------------------------------------------
# 封面页
# 要求：
# - 不改背景里的任何标题
# - 只加：
#     1) 「太郎 さん ＆ 花子 さん」在大标题「恋愛占星レポート」上方
#     2) 底部「作成日：YYYY年MM月DD日」
# ---------------------------------------------------------
def draw_cover_page(c: canvas.Canvas, male_name: str, female_name: str, created_at_jp: str):
    draw_full_bg(c, "cover.jpg")

    # 1) 姓名（在大标题上方，居中）
    names_text = f"{male_name} さん ＆ {female_name} さん"
    c.setFont(TITLE_FONT, 18)
    c.setFillColorRGB(0, 0, 0)

    # 估计位置：白色半透明区域上半部分，略高于金色大标题
    # A4 高度约 842，这里取 y ≈ 530，避免遮住背景上的标题
    name_y = 530
    name_width = pdfmetrics.stringWidth(names_text, TITLE_FONT, 18)
    name_x = (PAGE_WIDTH - name_width) / 2.0
    c.drawString(name_x, name_y, names_text)

    # 2) 作成日（底部中间）
    date_text = f"作成日：{created_at_jp}"
    c.setFont(BODY_FONT, 12)

    date_y = 135  # 对齐背景图里「作成日：   年   月   日」的位置
    date_width = pdfmetrics.stringWidth(date_text, BODY_FONT, 12)
    date_x = (PAGE_WIDTH - date_width) / 2.0
    c.drawString(date_x, date_y, date_text)

    c.showPage()


# ---------------------------------------------------------
# 说明页（page_summary.jpg）
# 内容现在只是示例，可以以后再换成真正的说明文
# ---------------------------------------------------------
def draw_intro_page(c: canvas.Canvas):
    draw_full_bg(c, "page_summary.jpg")

    c.setFont(BODY_FONT, 12)
    c.setFillColorRGB(0, 0, 0)

    text = (
        "このレポートは、お二人のホロスコープをもとに、\n"
        "性格やコミュニケーションの傾向、関係性のリズムを\n"
        "やさしく読み解くためのサンプルレポートです。"
    )

    x = 80
    y = 520
    for line in text.split("\n"):
        c.drawString(x, y, line)
        y -= 18

    c.showPage()


# ---------------------------------------------------------
# 星盘页：两个星盘一左一右，下面写名字
# 背景：page_basic.jpg
# 星盘底图：chart_base.png
# ---------------------------------------------------------
def draw_chart_page(c: canvas.Canvas, male_name: str, female_name: str):
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(app.static_folder, "assets", "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘大小（根据白色区域估一个安全值）
    chart_size = 210

    # 左右位置：留一点边距
    left_x = 70
    right_x = PAGE_WIDTH - 70 - chart_size

    # 垂直位置：大概在页面中部偏上
    center_y = 380
    bottom_y = center_y - chart_size / 2

    # 左侧星盘（男性）
    c.drawImage(chart_img, left_x, bottom_y, width=chart_size, height=chart_size, mask="auto")
    # 右侧星盘（女性）
    c.drawImage(chart_img, right_x, bottom_y, width=chart_size, height=chart_size, mask="auto")

    # 星盘下方名字
    c.setFont(BODY_FONT, 12)
    c.setFillColorRGB(0, 0, 0)

    male_label = f"{male_name} さん"
    female_label = f"{female_name} さん"

    male_label_width = pdfmetrics.stringWidth(male_label, BODY_FONT, 12)
    female_label_width = pdfmetrics.stringWidth(female_label, BODY_FONT, 12)

    male_label_x = left_x + chart_size / 2 - male_label_width / 2
    female_label_x = right_x + chart_size / 2 - female_label_width / 2

    label_y = bottom_y - 20

    c.drawString(male_label_x, label_y, male_label)
    c.drawString(female_label_x, label_y, female_label)

    c.showPage()


# ---------------------------------------------------------
# 其他页面：先按之前的背景一页一张，简单放一点示例文字
# 你以后可以只改文案，不用动代码结构
# ---------------------------------------------------------
def draw_communication_page(c: canvas.Canvas):
    draw_full_bg(c, "page_communication.jpg")
    c.setFont(BODY_FONT, 12)
    c.setFillColorRGB(0, 0, 0)

    text = (
        "ここにはお二人の会話のテンポや、\n"
        "気持ちが伝わりやすいコミュニケーションのポイントが入ります。"
    )
    x, y = 80, 520
    for line in text.split("\n"):
        c.drawString(x, y, line)
        y -= 18

    c.showPage()


def draw_points_page(c: canvas.Canvas):
    draw_full_bg(c, "page_points.jpg")
    c.setFont(BODY_FONT, 12)
    c.setFillColorRGB(0, 0, 0)

    text = (
        "ここには相性の良いところ・すれ違いやすいところなど、\n"
        "関係のポイントが箇条書きで入ります。"
    )
    x, y = 80, 520
    for line in text.split("\n"):
        c.drawString(x, y, line)
        y -= 18

    c.showPage()


def draw_trend_page(c: canvas.Canvas):
    draw_full_bg(c, "page_trend.jpg")
    c.setFont(BODY_FONT, 12)
    c.setFillColorRGB(0, 0, 0)

    text = (
        "このページには、今の関係の流れと\n"
        "これから一年くらいの傾向が入ります。"
    )
    x, y = 80, 520
    for line in text.split("\n"):
        c.drawString(x, y, line)
        y -= 18

    c.showPage()


def draw_advice_page(c: canvas.Canvas):
    draw_full_bg(c, "page_advice.jpg")
    c.setFont(BODY_FONT, 12)
    c.setFillColorRGB(0, 0, 0)

    text = (
        "ここには、日常で意識すると関係がよりスムーズになる\n"
        "具体的なアドバイスが入ります。"
    )
    x, y = 80, 520
    for line in text.split("\n"):
        c.drawString(x, y, line)
        y -= 18

    c.showPage()


def draw_summary_page(c: canvas.Canvas):
    draw_full_bg(c, "page_summary.jpg")
    c.setFont(BODY_FONT, 12)
    c.setFillColorRGB(0, 0, 0)

    text = (
        "このサンプルレポートは、テンプレートとフォントの\n"
        "動作確認用として作成されています。\n"
        "実際の鑑定では、お二人だけの文章がここに入ります。"
    )
    x, y = 80, 520
    for line in text.split("\n"):
        c.drawString(x, y, line)
        y -= 18

    c.showPage()


# ---------------------------------------------------------
# Flask 路由
# ---------------------------------------------------------

@app.route("/")
def root():
    return "PDF server running."


@app.route("/test.html")
def test_page():
    # 这只是之前的静态测试页，不动
    return app.send_static_file("test.html")


@app.route("/api/generate_report", methods=["GET"])
def generate_report():
    # 前端传进来的参数（可以先不管，默认值先写死）
    male_name = request.args.get("male_name", "太郎")
    female_name = request.args.get("female_name", "花子")

    # created_at：如果前端没传，就用今天
    created_raw = request.args.get("created_at")
    if created_raw:
        # 允许传 2025-01-01 或 2025/01/01
        created_raw = created_raw.replace("/", "-")
        dt = datetime.strptime(created_raw, "%Y-%m-%d")
    else:
        dt = datetime.now()
    created_at_jp = dt.strftime("%Y年%m月%d日")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # === 按顺序画每一页 ===
    draw_cover_page(c, male_name, female_name, created_at_jp)  # 1. 封面
    draw_intro_page(c)                                         # 2. 説明
    draw_chart_page(c, male_name, female_name)                 # 3. 星盤2つ
    draw_communication_page(c)                                 # 4. コミュニケーション
    draw_points_page(c)                                        # 5. 相性ポイント
    draw_trend_page(c)                                         # 6. 関係の流れ
    draw_advice_page(c)                                        # 7. アドバイス
    draw_summary_page(c)                                       # 8. まとめ

    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="love_report_sample.pdf",
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    # Render 上会用 gunicorn 启动；本地调试时用这个
    app.run(host="0.0.0.0", port=10000)

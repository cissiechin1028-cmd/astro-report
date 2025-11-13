from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

import io
import os
from datetime import datetime

# -------------------------------------------------
# Flask 基本设置
# -------------------------------------------------
app = Flask(__name__, static_url_path='', static_folder='public')

# 使用 ReportLab 自带日文字体（不会再用你上传的 Noto，因此不再报错）
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))     # 明朝体
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))  # ゴシック体

TITLE_FONT = "HeiseiKakuGo-W5"
BODY_FONT = "HeiseiMin-W3"

PAGE_WIDTH, PAGE_HEIGHT = A4  # 595 x 842 左右


# 简单工具：拼接 public/assets 路径
def asset_path(name: str) -> str:
    return os.path.join("public", "assets", name)


# -------------------------------------------------
# 封面页：只动姓名 + 作成日，别的保持背景
# -------------------------------------------------
def draw_cover_page(c, male_name: str, female_name: str, report_date: datetime):
    cover = asset_path("cover.jpg")
    c.drawImage(cover, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)

    # 颜色：接近金色 / 棕金，跟模板比较搭
    c.setFillColorRGB(0.45, 0.32, 0.18)

    # ① 姓名：放在「L O V E  R E P O R T」和「恋愛占星レポート」之间、
    #    略偏下，正好在大标题上方，不挡任何文字
    pair_label = f"{male_name} さん ＆ {female_name} さん"
    c.setFont(TITLE_FONT, 16)
    # 这个 Y 值你不满意我们再微调，现在大概在金色标题上方一点
    c.drawCentredString(PAGE_WIDTH / 2, 510, pair_label)

    # ② 作成日：用模板底部本来留空的那一条，置中显示
    date_label = report_date.strftime("作成日：%Y年%m月%d日")
    c.setFont(BODY_FONT, 12)
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_label)


# -------------------------------------------------
# 第 2 页：基本ホロスコープ + 双星盘，名字写在星盘下面
# -------------------------------------------------
def draw_horoscope_page(c, male_name: str, female_name: str):
    bg = asset_path("page_basic.jpg")
    c.drawImage(bg, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)

    chart_img = asset_path("chart_base.png")

    # 星盘大小稍微控制在半透明白框内
    chart_size = 260  # 正方形边长
    # 页面中线
    center_x = PAGE_WIDTH / 2

    # 左右星盘水平位置（中线左右各偏一点）
    gap = 40  # 中线与星盘之间的空隙
    left_x = center_x - chart_size - gap
    right_x = center_x + gap

    # 星盘竖直位置：大约在页面下半部分中间
    chart_y = 230

    # 绘制左、右星盘
    c.drawImage(chart_img, left_x, chart_y, width=chart_size, height=chart_size, mask='auto')
    c.drawImage(chart_img, right_x, chart_y, width=chart_size, height=chart_size, mask='auto')

    # 姓名放在各自星盘下方一点，不越出白色区域
    c.setFont(BODY_FONT, 12)
    c.setFillColorRGB(0.3, 0.2, 0.15)

    c.drawCentredString(left_x + chart_size / 2, chart_y - 24, f"{male_name} さん")
    c.drawCentredString(right_x + chart_size / 2, chart_y - 24, f"{female_name} さん")


# -------------------------------------------------
# 后面几页：先只铺背景，不额外加大标题
#（避免再覆盖你模板里的金色标题文字）
# -------------------------------------------------
def draw_empty_content_page(c, bg_filename: str):
    bg = asset_path(bg_filename)
    c.drawImage(bg, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT)
    # 你之后如果要在白色区域里填充文字，可以在这里追加小号文字绘制，
    # 但尽量别再画大字号标题，这样不会压住背景图自带的标题。


# -------------------------------------------------
# 生成 PDF 主函数
# -------------------------------------------------
def build_report_pdf(male_name: str, female_name: str, report_date: datetime) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # 1. 封面
    draw_cover_page(c, male_name, female_name, report_date)
    c.showPage()

    # 2. 基本ホロスコープ + 双星盘
    draw_horoscope_page(c, male_name, female_name)
    c.showPage()

    # 3. 性格・コミュニケーション（背景模板里已经有标题和说明）
    draw_empty_content_page(c, "page_communication.jpg")
    c.showPage()

    # 4. アドバイス
    draw_empty_content_page(c, "page_advice.jpg")
    c.showPage()

    # 5. 関係の流れ・今後の傾向
    draw_empty_content_page(c, "page_trend.jpg")
    c.showPage()

    # 6. 日常で役立つポイント
    draw_empty_content_page(c, "page_points.jpg")
    c.showPage()

    # 7. まとめ
    draw_empty_content_page(c, "page_summary.jpg")
    c.showPage()

    c.save()
    pdf_value = buffer.getvalue()
    buffer.close()
    return pdf_value


# -------------------------------------------------
# Flask 路由
# -------------------------------------------------

@app.route("/")
def root():
    return "Astro report PDF server running."


@app.route("/test.html")
def test_html():
    # 你之前的 test.html 静态文件
    return app.send_static_file("test.html")


@app.route("/api/generate_report", methods=["GET"])
def generate_report():
    # 名字默认给一个日文示例，没传也能出 demo
    male_name = request.args.get("male_name", "太郎")
    female_name = request.args.get("female_name", "花子")

    # 日期参数：?date=2025-01-01 这样的格式
    date_str = request.args.get("date")
    if date_str:
        try:
            report_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            report_date = datetime.now()
    else:
        report_date = datetime.now()

    pdf_bytes = build_report_pdf(male_name, female_name, report_date)

    return send_file(
        io.BytesIO(pdf_bytes),
        as_attachment=True,
        download_name="love_report_sample.pdf",
        mimetype="application/pdf"
    )


# 本地调试用（Render 会忽略这里）
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

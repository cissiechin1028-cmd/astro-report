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
JP_FONT = "HeiseiKakuGo-W5"   # 無衬线
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
# 小工具：日文段落换行
# ------------------------------------------------------------------
def draw_paragraph(c, text, x, y, max_width, line_height, font_name, font_size):
    """
    按 max_width 自动换行，适合日文/无空格文本。
    返回最后一行绘制完后的 y 坐标，方便继续往下画。
    """
    c.setFont(font_name, font_size)

    lines = []
    for raw_line in text.split("\n"):
        if not raw_line:
            # 空行：直接换一行
            lines.append("")
            continue

        buf = ""
        for ch in raw_line:
            w = c.stringWidth(buf + ch, font_name, font_size)
            if w <= max_width:
                buf += ch
            else:
                lines.append(buf)
                buf = ch
        lines.append(buf)

    for line in lines:
        c.drawString(x, y, line)
        y -= line_height

    return y


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
    c.setFillColorRGB(0.3, 0.3, 0.3)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    # 这个高度你刚才已经调好，如果想再微调就改这个数值
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    # 作成日：底部中央
    c.setFont(font, 12)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)

    c.showPage()

    # ------------------------------------------------------------------
    # 第 2 页：目次 / このレポートについて（index.jpg）
    # ------------------------------------------------------------------
    draw_full_bg(c, "index.jpg")
    c.setFillColorRGB(0, 0, 0)

    # 在 index 背景的文字框内写一段“このレポートの読み方”
    text_index = (
        "このレポートは、おふたりの太陽星座・月星座・上昇星座などをもとに、"
        "性格や感情表現の傾向、コミュニケーションのリズム、"
        "関係がスムーズになりやすいポイントをまとめたものです。\n\n"
        "結果は「当たり・外れ」を判断するためではなく、"
        "お互いを理解するための小さな地図としてお使いください。\n\n"
        "共感できる部分を大切にしながら、"
        "ふたりらしいペースで関係を育てていきましょう。"
    )
    # 位置稍微往下，避免顶到上面的标题
    draw_paragraph(
        c,
        text_index,
        x=80,
        y=620,
        max_width=PAGE_WIDTH - 160,
        line_height=18,
        font_name=font,
        font_size=11,
    )

    c.showPage()

    # ------------------------------------------------------------------
    # 第 3 页：基本ホロスコープと総合相性 + 两个星盘
    # 背景：page_basic.jpg
    # 星盘：chart_base.png 一左一右，下方分别写姓名
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_basic.jpg")

    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    # 星盘尺寸 + 位置（你之前已经大致确认过）
    chart_size = 180         # 直径
    left_x = 90              # 左边星盘的左上角 X
    left_y = 500             # 左右共同的 Y
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

    # 星盘下方姓名
    c.setFont(font, 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(left_x + chart_size / 2, left_y - 25, f"{male_name} さん")
    c.drawCentredString(right_x + chart_size / 2, right_y - 25, f"{female_name} さん")

    c.showPage()

    # ------------------------------------------------------------------
    # 第 4 页：性格とコミュニケーションの傾向（page_communication）
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_communication.jpg")
    c.setFillColorRGB(0, 0, 0)

    text_comm = (
        "ここでは、おふたりの性格のベースとコミュニケーションのリズムをまとめています。\n\n"
        "・話し方やテンポが似ている部分\n"
        "　→ 会話が自然に弾みやすく、沈黙も心地よく感じられるポイントです。\n\n"
        "・感じ方や大事にしているものが違う部分\n"
        "　→ 意見がぶつかりやすいところですが、視野を広げ合えるポイントでもあります。\n\n"
        "相手の「クセ」を知っておくことで、"
        "言い方を少し変えたり、タイミングを工夫したりと、"
        "小さな調整で関係がぐっとラクになります。"
    )

    draw_paragraph(
        c,
        text_comm,
        x=80,
        y=640,
        max_width=PAGE_WIDTH - 160,
        line_height=18,
        font_name=font,
        font_size=11,
    )

    c.showPage()

    # ------------------------------------------------------------------
    # 第 5 页：相性の良いところ・すれ違いやすいところ（page_points）
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_points.jpg")
    c.setFillColorRGB(0, 0, 0)

    text_points = (
        "ここでは、おふたりの相性の「良いところ」と、"
        "少しだけ意識しておきたい「すれ違いやすいポイント」を整理しています。\n\n"
        "【相性の良いところ】\n"
        "・一緒にいてホッとできる場面\n"
        "・価値観が自然と揃いやすい場面\n"
        "・相手の得意分野に素直に頼れる場面\n\n"
        "【すれ違いやすいところ】\n"
        "・言葉よりも態度で伝えがちな場面\n"
        "・どちらかが我慢しすぎてしまいがちな場面\n"
        "・タイミングの感覚がズレやすい場面\n\n"
        "「合わないところ」をなくすのではなく、"
        "お互いの違いを前提にした付き合い方を見つけていくことが、このページのテーマです。"
    )

    draw_paragraph(
        c,
        text_points,
        x=80,
        y=640,
        max_width=PAGE_WIDTH - 160,
        line_height=18,
        font_name=font,
        font_size=11,
    )

    c.showPage()

    # ------------------------------------------------------------------
    # 第 6 页：関係の流れと今後の傾向（page_trend）
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_trend.jpg")
    c.setFillColorRGB(0, 0, 0)

    text_trend = (
        "ここでは、おふたりの関係がどのような流れで進みやすいか、"
        "星の配置から読み取れるリズムをまとめています。\n\n"
        "・出会いの時期に強調されていたテーマ\n"
        "・距離が縮まりやすいタイミング\n"
        "・少し不安定になりやすい時期\n\n"
        "「今のステージ」を知っておくことで、"
        "焦らなくてよいことと、"
        "今だからこそ丁寧に向き合っておきたいポイントが見えてきます。"
    )

    draw_paragraph(
        c,
        text_trend,
        x=80,
        y=640,
        max_width=PAGE_WIDTH - 160,
        line_height=18,
        font_name=font,
        font_size=11,
    )

    c.showPage()

    # ------------------------------------------------------------------
    # 第 7 页：日常で役立つアドバイス（page_advice）
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_advice.jpg")
    c.setFillColorRGB(0, 0, 0)

    text_advice = (
        "ここからは、日常の中で取り入れやすい小さなアクションをお伝えします。\n\n"
        "・相手が安心しやすい言葉がけ\n"
        "・ケンカのあとに気持ちを整えるコツ\n"
        "・忙しい時期でもつながりを保つための工夫\n\n"
        "難しいことを急に変える必要はありません。"
        "まずは「今週できそうなこと」を一つだけ選んで試してみてください。"
    )

    draw_paragraph(
        c,
        text_advice,
        x=80,
        y=640,
        max_width=PAGE_WIDTH - 160,
        line_height=18,
        font_name=font,
        font_size=11,
    )

    c.showPage()

    # ------------------------------------------------------------------
    # 第 8 页：まとめ（page_summary）
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_summary.jpg")
    c.setFillColorRGB(0, 0, 0)

    text_summary = (
        "最後に、このレポート全体のまとめです。\n\n"
        "占いの結果は、ふたりの未来を決めつけるものではなく、"
        "より心地よい関係をつくるためのヒント集です。\n\n"
        "お互いの違いを知り、共通点を見つけ、"
        "ときどき立ち止まりながらも、一緒に進んでいけるかどうかが何より大切です。\n\n"
        "このレポートが、おふたりのこれからの日々に、"
        "少しでも安心とあたたかさをもたらすことができれば幸いです。"
    )

    draw_paragraph(
        c,
        text_summary,
        x=80,
        y=640,
        max_width=PAGE_WIDTH - 160,
        line_height=18,
        font_name=font,
        font_size=11,
    )

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

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
# 字体设置
#   JP_SANS  : 粗一点的黑体（标题用）
#   JP_SERIF : 细一点的明朝体（正文、第三页用）
# ------------------------------------------------------------------
JP_SANS = "HeiseiKakuGo-W5"
JP_SERIF = "HeiseiMin-W3"
pdfmetrics.registerFont(UnicodeCIDFont(JP_SANS))
pdfmetrics.registerFont(UnicodeCIDFont(JP_SERIF))


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
# 小工具：文本自动换行（第 4～6 页通用）
# ------------------------------------------------------------------
def draw_wrapped_block(c, text, x, y_start, wrap_width,
                       font_name, font_size, line_height):
    """
    在 (x, y_start) 开始画一段文字，按字符宽度自动换行。
    返回最后一行画完后的下一行 y 坐标（方便接着往下画）。
    """
    c.setFont(font_name, font_size)
    line = ""
    y = y_start

    for ch in text:
        if ch == "\n":
            # 手动换行
            c.drawString(x, y, line)
            line = ""
            y -= line_height
            continue

        new_line = line + ch
        if pdfmetrics.stringWidth(new_line, font_name, font_size) <= wrap_width:
            line = new_line
        else:
            c.drawString(x, y, line)
            line = ch
            y -= line_height

    if line:
        c.drawString(x, y, line)
        y -= line_height

    return y


# ------------------------------------------------------------------
# 行数限制版：最多画 max_lines 行（第 6 页表格用）
# ------------------------------------------------------------------
def draw_wrapped_block_limited(
    c,
    text,
    x,
    y_start,
    wrap_width,
    font_name,
    font_size,
    line_height,
    max_lines,
):
    """
    在 (x, y_start) 开始画一段文字，自动换行，但最多画 max_lines 行。
    返回最后一行画完后的下一行 y 坐标。
    """
    c.setFont(font_name, font_size)
    line = ""
    y = y_start
    lines = 0

    for ch in text:
        if ch == "\n":
            c.drawString(x, y, line)
            line = ""
            y -= line_height
            lines += 1
            if lines >= max_lines:
                return y
            continue

        new_line = line + ch
        if pdfmetrics.stringWidth(new_line, font_name, font_size) <= wrap_width:
            line = new_line
        else:
            c.drawString(x, y, line)
            line = ch
            y -= line_height
            lines += 1
            if lines >= max_lines:
                return y

    if line and lines < max_lines:
        c.drawString(x, y, line)
        y -= line_height

    return y


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

    # ------------------------------------------------------------------
    # 封面：cover.jpg
    # ------------------------------------------------------------------
    draw_full_bg(c, "cover.jpg")

    # 姓名：恋愛占星レポート 正上方（字体颜色整体调浅一点）
    c.setFont(JP_SANS, 18)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    # 作成日：底部中央
    c.setFont(JP_SANS, 12)
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

    # 星盘尺寸 + 位置（使用你现在这版的坐标）
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

    # ------------------ 星盘下方姓名（用细明朝体） ------------------
    c.setFont(JP_SERIF, 14)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(left_cx, left_y - 25, f"{male_name} さん")
    c.drawCentredString(right_cx, right_y - 25, f"{female_name} さん")

    # ------------------ 星盘下方 5 行列表（用细明朝体，左对齐） ------------------
    c.setFont(JP_SERIF, 8.5)
    c.setFillColorRGB(0.2, 0.2, 0.2)

    male_lines = [info["label"] for info in male_planets.values()]
    for i, line in enumerate(male_lines):
        y = left_y - 45 - i * 11
        c.drawString(left_cx - 30, y, line)

    female_lines = [info["label"] for info in female_planets.values()]
    for i, line in enumerate(female_lines):
        y = right_y - 45 - i * 11
        c.drawString(right_cx - 30, y, line)

    # ------------------------------------------------------------------
    # 星盘下方：総合相性スコア ＋ 太陽・月・上昇の分析
    # ------------------------------------------------------------------
    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    c.setFont(body_font, body_size)
    c.setFillColorRGB(0.2, 0.2, 0.2)

    # ===== 総合相性スコア =====
    score_y = 330  # 可以视效果微调
    overall_score = 82  # ★ 这里是总分（0〜100），需要的话你可以自己改数字
    score_text = f"総合相性スコア：{overall_score} / 100"
    c.drawString(text_x, score_y, score_text)

    # 不超过两行的总结
    summary_score = (
        "安心感とやさしさのバランスがよく、"
        "長く付き合うほどお互いの良さを引き出し合える相性です。"
    )
    y_score = score_y - line_height
    y_score = draw_wrapped_block(
        c,
        summary_score,
        text_x,
        y_score,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )

    # ===== 太陽・月・上昇の分析 =====
    y_analysis = y_score - line_height  # 总结和下面标题之间留一点空隙
    c.setFont(body_font, body_size)
    c.drawString(text_x, y_analysis, "太陽・月・上昇の分析")
    y_analysis -= line_height

    # 太陽：约两行
    block_sun = (
        "太陽：牡羊座の太郎 さんと蟹座の花子 さんは、"
        "行動力と包容力が補い合う組み合わせです。"
    )
    y_analysis = draw_wrapped_block(
        c,
        block_sun,
        text_x,
        y_analysis,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y_analysis -= line_height * 0.6  # 小间距

    # 月：约两行
    block_moon = (
        "月：双子座と乙女座の月は、言葉で気持ちを共有することが鍵。"
        "こまめな対話が安心感を深めてくれます。"
    )
    y_analysis = draw_wrapped_block(
        c,
        block_moon,
        text_x,
        y_analysis,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y_analysis -= line_height * 0.6

    # 上昇：约两行
    block_asc = (
        "上昇：山羊座と魚座のASCは、慎重さとやさしさが調和するペア。"
        "時間をかけて信頼を育てていくタイプです。"
    )
    y_analysis = draw_wrapped_block(
        c,
        block_asc,
        text_x,
        y_analysis,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )

    c.showPage()

        # ------------------------------------------------------------------
    # 第 4 页：性格の違いとコミュニケーション
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_communication.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130          # 左边起点（跟小标题差不多一条线）
    wrap_width = 360      # 行宽稍微拉长一点
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    # ===== 話し方とテンポ =====
    y = 625
    body_1 = (
        "太郎 さんは、自分の気持ちを言葉にするまでに少し時間をかける、"
        "じっくりタイプです。一方で、花子 さんは、その場で感じたことをすぐに言葉にする、"
        "テンポの速いタイプです。日常会話では、片方が考えている間にもう一方がどんどん話してしまい、"
        "「ちゃんと聞いてもらえていない」と感じる場面が出やすくなります。"
    )
    summary_1 = (
        "一言でいうと、二人の話し方は「スピードの違いを理解し合うことで"
        "心地よくつながれるペア」です。"
    )
    y = draw_wrapped_block(c, body_1, text_x, y, wrap_width,
                           body_font, body_size, line_height)
    y -= line_height
    draw_wrapped_block_limited(c, summary_1, text_x, y, wrap_width,
                               body_font, body_size, line_height, 2)

    # ===== 問題への向き合い方 =====
    y2 = 434
    body_2 = (
        "太郎 さんは、問題が起きたときにまず全体を整理してから、落ち着いて対処しようとします。"
        "花子 さんは、感情の動きに敏感で、まず気持ちを共有したいタイプです。"
        "同じ出来事でも、片方は「どう解決するか」、もう片方は「どう感じたか」を大事にするため、"
        "タイミングがずれると、すれ違いが生まれやすくなります。"
    )
    summary_2 = (
        "一言でいうと、二人は「解決志向」と「共感志向」が支え合う、"
        "心強いバランス型のペアです。"
    )
    y2 = draw_wrapped_block(c, body_2, text_x, y2, wrap_width,
                            body_font, body_size, line_height)
    y2 -= line_height
    draw_wrapped_block_limited(c, summary_2, text_x, y2, wrap_width,
                               body_font, body_size, line_height, 2)

    # ===== 価値観のズレ =====
    y3 = 236
    body_3 = (
        "太郎 さんは、安定や責任感を重视する一方で、花子 さんは、変化やワクワク感を大切にする傾向があります。"
        "お金の使い方や休日の过ごし方、将来のイメージなど、小さな違いが積み重なると、"
        "「なんでわかってくれないの？」と感じる瞬間が出てくるかもしれません。"
    )
    summary_3 = (
        "一言でいうと、二人の価値観は違いを否定するのではなく、"
        "「お互いの世界を広げ合うきっかけ」になる組み合わせです。"
    )
    y3 = draw_wrapped_block(c, body_3, text_x, y3, wrap_width,
                            body_font, body_size, line_height)
    y3 -= line_height
    draw_wrapped_block_limited(c, summary_3, text_x, y3, wrap_width,
                               body_font, body_size, line_height, 2)

    c.showPage()

        # ------------------------------------------------------------------
    # 第 5 页：ふたりの強みと課題ポイント
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_points.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    # ===== ふたりの「いいところ」 =====
    y = 625
    body_4 = (
        "太郎 さんは、相手の立場を考えながら行動できる、落ち着いた安心感のあるタイプです。"
        "花子 さんは、その場の空気を明るくし、素直な気持ちを伝えられるタイプです。"
        "二人が一緒にいると、「安心感」と「温かさ」が自然と周りにも伝わり、"
        "お互いの長所を引き出し合える関係になりやすい組み合わせです。"
    )
    summary_4 = (
        "一言でいうと、二人は「一緒にいるだけで場がやわらぎ、"
        "温かさが自然と伝わっていくペア」です。"
    )
    y = draw_wrapped_block(c, body_4, text_x, y, wrap_width,
                           body_font, body_size, line_height)
    y -= line_height
    draw_wrapped_block(c, summary_4, text_x, y, wrap_width,
                       body_font, body_size, line_height)

    # ===== すれ違いやすいポイント =====
    y2 = 434
    body_5 = (
        "太郎 さんは、物事を決めるときに慎重に考えたいタイプで、"
        "花子 さんは、流れや直感を大切にして「とりあえずやってみよう」と思うことが多いかもしれません。"
        "そのため、決断のペースや優先順位がずれると、"
        "「どうしてそんなに急ぐの？」「どうしてそんなに慎重なの？」とお互いに感じやすくなります。"
    )
    summary_5 = (
        "一言でいうと、二人のすれ違いは「慎重さ」と「フットワークの軽さ」の差ですが、"
        "そのギャップは視野を広げるヒントにもなります。"
    )
    y2 = draw_wrapped_block(c, body_5, text_x, y2, wrap_width,
                            body_font, body_size, line_height)
    y2 -= line_height
    draw_wrapped_block(c, summary_5, text_x, y2, wrap_width,
                       body_font, body_size, line_height)

    # ===== 伸ばしていけるポイント =====
    y3 = 236
    body_6 = (
        "太郎 さんの安定感と、花子 さんの柔軟さ・明るさが合わさることで、"
        "二人は「現実的で無理のないチャレンジ」を積み重ねていけるペアです。"
        "お互いの考え方を一度言葉にして共有する習慣ができると、"
        "二人だけのペースや目標が見つかり、将来像もより具体的に描きやすくなります。"
    )
    summary_6 = (
        "一言でいうと、二人の伸ばしていけるポイントは「安心できる土台の上で、"
        "新しい一歩を一緒に踏み出せる力」です。"
    )
    y3 = draw_wrapped_block(c, body_6, text_x, y3, wrap_width,
                            body_font, body_size, line_height)
    y3 -= line_height
    draw_wrapped_block(c, summary_6, text_x, y3, wrap_width,
                       body_font, body_size, line_height)

    c.showPage()


            # ------------------------------------------------------------------
    # 第 6 页：関係の方向性と今後の傾向
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_trend.jpg")
    # 整页文字颜色稍微调浅一点
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    # ===== 今の関係ステージ =====
    y = 620
    body_stage = (
        "今の二人の関係は、日常の中に安心感がありつつも、"
        "まだお互いを深く知っていく途中のステージにあります。"
        "気軽さとドキドキ感が同居している時期ともいえます。"
    )
    summary_stage = (
        "一言でいうと、「落ち着きつつも、まだ伸びしろの多い関係」です。"
    )

    y = draw_wrapped_block(c, body_stage, text_x, y,
                           wrap_width, body_font, body_size, line_height)
    y -= line_height
    draw_wrapped_block(c, summary_stage, text_x, y,
                       wrap_width, body_font, body_size, line_height)

    # ===== 発展の流れ（中央の表） =====
    # 整个区块往上移一点：原来 460 → 466
    y2 = 466
    body_flow = (
        "二人の関係は、出会い期・成長期・安定期という流れの中で、"
        "少しずつお互いのペースが見えてくるタイプです。"
    )
    y2 = draw_wrapped_block(c, body_flow, text_x, y2,
                            wrap_width, body_font, body_size, line_height)

    # ★ 说明文字和整张表格之间的间距
    #   数字越大，整张表（段階/特徴+三行+三条线）越往下
    table_top = y2 - line_height * 1.6

    # 表头：段階／特徴
    c.setFont(body_font, body_size)
    header_base = table_top
    c.drawString(text_x, header_base, "段階")
    c.drawString(text_x + 80, header_base, "特徴")

    # 线条颜色 & 粗细（维持你现在的浅灰色）
    c.setStrokeColorRGB(0.9, 0.9, 0.9)
    c.setLineWidth(0.4)

    # 表头下面的第一条横线
    c.line(text_x, header_base - 4, text_x + wrap_width, header_base - 4)

    # 第 1 行数据 baseline（从表头再往下 1 行）
    y2 = header_base - line_height

    # ===== 三阶段文字（最多 2 行）=====
    rows = [
        ("出会い期",
         "最初はお互いの新鮮さが強く、ドキドキや憧れが中心になります。"
         "第一印象が固まりやすい時期です。"),

        ("成長期",
         "相手の弱さや価値観の違いが見えてきて、摩擦と理解をくり返しながら関係を深めていく時期です。"),

        ("安定期",
         "お互いのペースや居場所がわかってきて、安心感と居心地の良さがベースになる時期です。"),
    ]
    max_lines = 2

    for label, desc in rows:
        row_top = y2

        c.setFont(body_font, body_size)
        c.drawString(text_x, row_top, label)

        draw_wrapped_block_limited(
            c,
            desc,
            text_x + 80,
            row_top,
            wrap_width - 80,
            body_font,
            body_size,
            line_height,
            max_lines,
        )

        y2 = row_top - max_lines * line_height

        c.line(text_x, y2 + 4, text_x + wrap_width, y2 + 4)

        y2 -= line_height

    # ===== バランスを保つコツ =====
    y3 = 170
    body_tip = (
        "二人が長く心地よく付き合っていくためには、"
        "どちらか一方のペースや考えに寄りかかりすぎないことがポイントになります。"
        "ときどき立ち止まって、「今どんな気持ち？」と確認し合うことで、"
        "小さなモヤモヤを大きなすれ違いになる前にケアできます。"
    )

    # 只保留一段
    y3 = draw_wrapped_block(c, body_tip, text_x, y3,
                            wrap_width, body_font, body_size, line_height)

    c.showPage()

    # ------------------------------------------------------------------
    # 第 7・8 页：只铺背景
    # ------------------------------------------------------------------
    for bg in ["page_advice.jpg", "page_summary.jpg"]:
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


# ------------------------------------------------------------------
# 主程序入口（必须顶格）
# ------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

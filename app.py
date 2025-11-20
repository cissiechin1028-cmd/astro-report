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
# 小工具：文本自动换行
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
# 行数限制版：最多画 max_lines 行
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
# 小工具：页码（从第 3 页开始用）
# ------------------------------------------------------------------
def draw_page_number(c, page_num: int):
    c.setFont(JP_SANS, 10)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawCentredString(PAGE_WIDTH / 2, 40, str(page_num))


# ------------------------------------------------------------------
# 根路径 & test.html
# ------------------------------------------------------------------
@app.route("/")
def root():
    return "PDF server running."


@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")


# ==============================================================
#           第 3〜7 页：页面绘制函数
# ==============================================================

# ------------------------------------------------------------------
# Page3 用：相性スコア + 太陽・月・ASC のテキスト + 星盤描画
# ------------------------------------------------------------------

# 12星座 → 4元素
SIGN_ELEMENT = {
    "牡羊座": "fire",
    "牡牛座": "earth",
    "双子座": "air",
    "蟹座":   "water",
    "獅子座": "fire",
    "乙女座": "earth",
    "天秤座": "air",
    "蠍座":   "water",
    "射手座": "fire",
    "山羊座": "earth",
    "水瓶座": "air",
    "魚座":   "water",
}

# 元素の組み合わせごとの相性まとめ（2文以内）
PAIR_SUMMARY_TEXT = {
    # fire × fire
    ("fire", "fire"):
        "情熱と勢いで惹かれ合う、華やかなペアです。"
        "お互いが主役になりやすいので、ときどきペースを落として相手の気持ちを聞けると長続きします。",

    # fire × earth
    ("fire", "earth"):
        "片方の情熱と片方の安定感が、良いバランスを生み出すペアです。"
        "勢いだけで突っ走らず、現実的な計画を一緒に立てることで関係が育ちやすくなります。",

    # fire × air
    ("fire", "air"):
        "ノリとアイデアで世界を広げていける、刺激的なペアです。"
        "その場の勢いで決めすぎず、ときどき未来のビジョンをすり合わせると安心感も高まります。",

    # fire × water
    ("fire", "water"):
        "情熱と感受性が混ざり合う、ドラマチックなペアです。"
        "感情がぶつかりやすいぶん、相手のペースを尊重してあげると深い信頼につながります。",

    # earth × fire
    ("earth", "fire"):
        "堅実さと行動力で、現実をしっかり動かしていけるペアです。"
        "慎重さとチャレンジ精神の両方を大事にすると、長期的なパートナーシップになりやすいタイプです。",

    # earth × earth
    ("earth", "earth"):
        "価値観や生活リズムが似やすい、安心感の高いペアです。"
        "安定を大切にしつつ、ときどき小さな変化や楽しみを共有するとマンネリを防げます。",

    # earth × air
    ("earth", "air"):
        "片方が現実を支え、片方が視野を広げる、補い合いのペアです。"
        "考え方の違いを否定せず、「役割分担」として受け止めると心地よい距離感が育ちます。",

    # earth × water
    ("earth", "water"):
        "現実感と優しさで、ほっとできる居場所をつくれるペアです。"
        "感情を我慢しすぎず、素直な気持ちを言葉にすることで、さらに信頼が深まっていきます。",

    # air × fire
    ("air", "fire"):
        "会話と行動力で世界をどんどん広げていける、冒険タイプのペアです。"
        "テンションの差が出たときは、相手のモードを確認してから動くとすれ違いが減ります。",

    # air × earth
    ("air", "earth"):
        "アイデアと現実性を組み合わせて、着実に形にできるペアです。"
        "理屈と感覚の両方を尊重しながら話し合うことで、安定と自由のバランスが整っていきます。",

    # air × air
    ("air", "air"):
        "価値観や会話のテンポが似やすく、一緒にいて気楽なペアです。"
        "話すだけで終わらず、小さな約束を実行していくと信頼感がより強くなります。",

    # air × water
    ("air", "water"):
        "片方が言葉で整理し、片方が気持ちで寄り添う、心のサポート力の高いペアです。"
        "感情と理性のギャップを責め合わず、「お互いの強み」として活かすと絆が深まります。",

    # water × fire
    ("water", "fire"):
        "感情の深さと情熱が混ざり合う、印象的なペアです。"
        "ムードに流されすぎず、安心できるルールやペースを共有すると長く続きやすくなります。",

    # water × earth
    ("water", "earth"):
        "優しさと安定感で、落ち着いた関係を育てていけるペアです。"
        "気遣いで我慢しすぎず、ときどき本音を打ち明けることで心の距離がさらに縮まります。",

    # water × air
    ("water", "air"):
        "感性と知性がお互いを刺激し合う、化学反応タイプのペアです。"
        "感じ方の違いを説明し合う時間をつくると、誤解が減って支え合いやすくなります。",

    # water × water
    ("water", "water"):
        "感情の波を分かち合える、共感力の高いペアです。"
        "ふたりとも疲れているときは、言葉より休息を優先するなど、セルフケアを共有できると安心感が続きます。",
}


def build_pair_summary_from_sun(male_sun_ja: str, female_sun_ja: str) -> str:
    """
    太陽星座（日本語名）から、元素を見て相性まとめ文を返す。
    戻り値は 2 文以内。
    """
    em = SIGN_ELEMENT.get(male_sun_ja)
    ef = SIGN_ELEMENT.get(female_sun_ja)

    if em is None or ef is None:
        # 万が一星座が取れなかったときの予備
        return (
            "お互いの違いを通して、新しい価値観を学び合えるペアです。"
            "少しずつ歩調を合わせていくことで、安心できる関係が育っていきます。"
        )

    base_text = PAIR_SUMMARY_TEXT.get((em, ef))
    if base_text is None:
        base_text = (
            "お互いの個性を活かしながら、ほどよい距離感で支え合えるペアです。"
            "違いを否定せず、興味を持って聞き合うことで信頼が深まります。"
        )

    # ここではあえて星座名を入れず、「2文以内」に収める
    return base_text


def build_page3_texts(male_name: str,
                      female_name: str,
                      male_core: dict,
                      female_core: dict):
    """
    第3ページ用のテキスト一式をまとめて生成する。

    戻り値:
      compat_score   : 数値スコア (80〜92)  ※ 今はレイアウト維持用のダミー値
      compat_summary : 一言の相性まとめ（太陽星座×太陽星座で 2 文）
      sun_text       : 太陽サインの説明
      moon_text      : 月サインの説明
      asc_text       : ASC の説明
    """

    # ① 太陽星座 → 元素 → 相性まとめ（2 文以内）
    male_sun_ja = male_core.get("sun", {}).get("name_ja")
    female_sun_ja = female_core.get("sun", {}).get("name_ja")
    compat_summary = build_pair_summary_from_sun(male_sun_ja, female_sun_ja)

    # ② スコアはとりあえず固定値（デザイン崩さないためのダミー）
    compat_score = 88

    # ③ 太陽テキスト（名前だけ実データ差し込み）
    sun_text = (
        "太陽（ふたりの価値観）："
        f"{male_name} さんは安定感と責任感を、"
        f"{female_name} さんは素直さとあたたかさを大切にするタイプです。"
    )

    # ④ 月テキスト
    moon_text = (
        "月（素の感情と安心ポイント）："
        f"{male_name} さんは落ち着いた空間やペースを守れる関係に安心し、"
        f"{female_name} さんは気持ちをその場で分かち合えることに"
        "心地よさを感じやすい傾向があります。"
    )

    # ⑤ ASC テキスト
    asc_text = (
        "ASC（第一印象・ふたりの雰囲気）："
        "出会ったときの印象は、周りから見ると「穏やかだけれど芯のあるペア」。"
        "少しずつ素の表情が見えるほど、二人らしい雰囲気が育っていきます。"
    )

    # ⑥ generate_report 側のアンパックと対応させるため、必ず 5 つ返す
    return compat_score, compat_summary, sun_text, moon_text, asc_text



# ------------------------------------------------------------------
# 星座 → 星座中点の「擬似度数」（本物の度数は使わない簡易星盤）
# ------------------------------------------------------------------
SIGN_CENTER_DEG = {
    "牡羊座": 15,
    "牡牛座": 45,
    "双子座": 75,
    "蟹座": 105,
    "獅子座": 135,
    "乙女座": 165,
    "天秤座": 195,
    "蠍座": 225,
    "射手座": 255,
    "山羊座": 285,
    "水瓶座": 315,
    "魚座": 345,
}


def fake_deg_from_sign_dict(d: dict) -> float:
    """
    d = {"lon": ..., "name_ja": "..."} みたいな dict から、
    name_ja（星座名）だけを見て「その星座扇形の真ん中の度数」を返す。
    lon は無視する（本物の度数を使わない簡易版）。
    """
    sign = d.get("name_ja")
    return SIGN_CENTER_DEG.get(sign, 0.0)


def build_planet_block(core: dict) -> dict:
    """
    core = {
        "sun":   {"lon":..., "name_ja":...},
        "moon":  {...},
        "venus": {...},
        "mars":  {...},
        "asc":   {...},
    }
    という形の dict を、描画用に整える。
    """

    # 文本：只显示星座名，不显示度数
    def fmt(label_ja: str, d: dict) -> str:
        # 原来是：f"{label_ja}：{d['name_ja']} {d['lon']:.1f}°"
        return f"{label_ja}：{d['name_ja']}"

    return {
        "sun": {
            # ★ 用星座中点的假度数画图标
            "deg": fake_deg_from_sign_dict(core["sun"]),
            "label": fmt("太陽", core["sun"]),
        },
        "moon": {
            "deg": fake_deg_from_sign_dict(core["moon"]),
            "label": fmt("月", core["moon"]),
        },
        "venus": {
            "deg": fake_deg_from_sign_dict(core["venus"]),
            "label": fmt("金星", core["venus"]),
        },
        "mars": {
            "deg": fake_deg_from_sign_dict(core["mars"]),
            "label": fmt("火星", core["mars"]),
        },
        "asc": {
            "deg": fake_deg_from_sign_dict(core["asc"]),
            "label": fmt("ASC", core["asc"]),
        },
    }


def draw_page3_basic_and_synastry(
    c,
    male_name: str,
    female_name: str,
    male_core: dict,
    female_core: dict,
    compat_score: int,
    compat_summary: str,
    sun_text: str,
    moon_text: str,
    asc_text: str,
):
    """
    PDF 第3ページを丸ごと描画する。
    - 左右のホロスコープ（ここでは「星座中点の擬似度数」でプロット）
    - 下部に総合相性スコア
    - 太陽 / 月 / ASC の文章（3ブロック）
    """
    # 背景
    draw_full_bg(c, "page_basic.jpg")

    # 星盤のベース画像
    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")
    chart_img = ImageReader(chart_path)

    chart_size = 180
    left_x = 90
    left_y = 520
    right_x = PAGE_WIDTH - chart_size - 90
    right_y = left_y

    # 中心座標
    left_cx = left_x + chart_size / 2
    left_cy = left_y + chart_size / 2
    right_cx = right_x + chart_size / 2
    right_cy = right_y + chart_size / 2

    # ベース画像を描画
    c.drawImage(chart_img, left_x, left_y,
                width=chart_size, height=chart_size, mask="auto")
    c.drawImage(chart_img, right_x, right_y,
                width=chart_size, height=chart_size, mask="auto")

    # 行星データ（ここに「简易星盤 core」が入ってくる）
    male_planets = build_planet_block(male_core)
    female_planets = build_planet_block(female_core)

    # アイコンファイル
    icon_files = {
        "sun": "icon_sun.png",
        "moon": "icon_moon.png",
        "venus": "icon_venus.png",
        "mars": "icon_mars.png",
        "asc": "icon_asc.png",
    }

    # 男 = 青系 / 女 = ピンク系
    male_color = (0.15, 0.45, 0.9)
    female_color = (0.9, 0.35, 0.65)

    # 星盤にプロット（男）
    for key, info in male_planets.items():
        draw_planet_icon(
            c,
            left_cx,
            left_cy,
            chart_size,
            info["deg"],      # ★ 星座中点の擬似度数
            male_color,
            icon_files[key],
        )

    # 星盤にプロット（女）
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

    # 星盤下の名前
    c.setFont(JP_SERIF, 14)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(left_cx, left_y - 25, f"{male_name} さん")
    c.drawCentredString(right_cx, right_y - 25, f"{female_name} さん")

    # 星盤下の 5 行（太陽〜ASC）—— 只显示星座名
    c.setFont(JP_SERIF, 8.5)
    male_lines = [info["label"] for info in male_planets.values()]
    for i, line in enumerate(male_lines):
        y = left_y - 45 - i * 11
        c.drawString(left_cx - 30, y, line)

    female_lines = [info["label"] for info in female_planets.values()]
    for i, line in enumerate(female_lines):
        y = right_y - 45 - i * 11
        c.drawString(right_cx - 30, y, line)

    # 下部テキストブロック
    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    # 相性まとめ（数値スコアは出さない）
c.setFont(JP_SANS, 12)
c.setFillColorRGB(0.2, 0.2, 0.2)
c.drawString(text_x, 350, "ふたりの相性バランス：")

    # 一言まとめ（最大2行）
    draw_wrapped_block_limited(
        c,
        compat_summary,
        text_x,
        350 - line_height * 1.4,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=2,
    )



    # 太陽・月・ASC の分析（各ブロック最大 3 行まで）
    y_analysis = 220
    c.setFont(body_font, body_size)
    for block_text in (sun_text, moon_text, asc_text):
        y_analysis = draw_wrapped_block_limited(
            c,
            block_text,
            text_x,
            y_analysis,
            wrap_width,
            body_font,
            body_size,
            line_height,
            max_lines=3,
        )
        y_analysis -= line_height  # ブロック間の余白

    # ページ番号
    draw_page_number(c, 3)
    c.showPage()


# ------------------------------------------------------------------
# 第 4 页：性格の違いとコミュニケーション（变量版）
# ------------------------------------------------------------------
def draw_page4_communication(
    c,
    talk_text, talk_summary,
    problem_text, problem_summary,
    values_text, values_summary,
):
    draw_full_bg(c, "page_communication.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    # 話し方とテンポ
    y = 625
    y = draw_wrapped_block(
        c,
        talk_text,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height
    )
    y -= line_height
    draw_wrapped_block_limited(
        c,
        talk_summary,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1
    )

    # 問題への向き合い方
    y2 = 434
    y2 = draw_wrapped_block(
        c,
        problem_text,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height
    )
    y2 -= line_height
    draw_wrapped_block_limited(
        c,
        problem_summary,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1
    )

    # 価値観のズレ
    y3 = 236
    y3 = draw_wrapped_block(
        c,
        values_text,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height
    )
    y3 -= line_height
    draw_wrapped_block_limited(
        c,
        values_summary,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1
    )

    draw_page_number(c, 4)
    c.showPage()


# ------------------------------------------------------------------
# 第 5 页：相性の良い点・すれ違いやすい点（变量版）
# ------------------------------------------------------------------
def draw_page5_points(
    c,
    good_text, good_summary,
    gap_text, gap_summary,
    hint_text, hint_summary,
):
    draw_full_bg(c, "page_points.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    # 相性の良いところ
    y = 625
    y = draw_wrapped_block(
        c,
        good_text,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y -= line_height
    draw_wrapped_block_limited(
        c,
        good_summary,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    # すれ違いやすいところ
    y2 = 434
    y2 = draw_wrapped_block(
        c,
        gap_text,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y2 -= line_height
    draw_wrapped_block_limited(
        c,
        gap_summary,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    # 関係をスムーズにするヒント
    y3 = 236
    y3 = draw_wrapped_block(
        c,
        hint_text,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y3 -= line_height
    draw_wrapped_block_limited(
        c,
        hint_summary,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    draw_page_number(c, 5)
    c.showPage()


# ------------------------------------------------------------------
# 第 6 页：関係の方向性と今後の傾向（变量版）
# ------------------------------------------------------------------
def draw_page6_trend(
    c,
    theme_text, theme_summary,
    emotion_text, emotion_summary,
    style_text, style_summary,
    future_text, future_summary,
):
    draw_full_bg(c, "page_trend.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    text_x = 130
    wrap_width = 360
    body_font = JP_SERIF
    body_size = 12
    line_height = 18

    # ① 二人の関係テーマ
    y = 620
    y = draw_wrapped_block(
        c,
        theme_text,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y -= line_height
    draw_wrapped_block_limited(
        c,
        theme_summary,
        text_x,
        y,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    # ② 感情の流れ・深まり方
    y2 = 460
    y2 = draw_wrapped_block(
        c,
        emotion_text,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y2 -= line_height
    draw_wrapped_block_limited(
        c,
        emotion_summary,
        text_x,
        y2,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    # ③ 二人が築いていくスタイル
    y3 = 300
    y3 = draw_wrapped_block(
        c,
        style_text,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y3 -= line_height
    draw_wrapped_block_limited(
        c,
        style_summary,
        text_x,
        y3,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    # ④ 今後 1〜2 年の関係傾向
    y4 = 145
    y4 = draw_wrapped_block(
        c,
        future_text,
        text_x,
        y4,
        wrap_width,
        body_font,
        body_size,
        line_height,
    )
    y4 -= line_height
    draw_wrapped_block_limited(
        c,
        future_summary,
        text_x,
        y4,
        wrap_width,
        body_font,
        body_size,
        line_height,
        max_lines=1,
    )

    draw_page_number(c, 6)
    c.showPage()


# ------------------------------------------------------------------
# 第 7 页：日常で役立つアドバイス（变量版）
# ------------------------------------------------------------------
def draw_page7_advice(c, advice_rows, footer_text):
    """
    advice_rows: [(scene_text, tip_text), ...]  左列 + 右列 的列表
    footer_text: 最下方那段 2 行以内的小总结
    """
    draw_full_bg(c, "page_advice.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    # 表整体设置
    table_x = 130
    table_width = 360
    col1_width = 140
    col_gap = 20
    col2_width = table_width - col1_width - col_gap

    body_font = JP_SERIF
    body_size = 11
    line_height = 16

    header_y = 680

    # 表头
    header_font_size = body_size + 2
    c.setFont(JP_SANS, header_font_size)
    c.drawString(table_x, header_y, "ふたりのシーン")
    c.drawString(table_x + col1_width + col_gap, header_y, "うまくいくコツ")

    # 横线
    c.setStrokeColorRGB(0.9, 0.9, 0.9)
    c.setLineWidth(0.4)
    c.line(table_x, header_y - 8, table_x + table_width, header_y - 8)

    # 内容行起始位置
    y_row = header_y - line_height * 1.8

    c.setFont(body_font, body_size)

    for scene_text, tip_text in advice_rows:
        row_top = y_row

        scene_y = draw_wrapped_block(
            c,
            scene_text,
            table_x,
            row_top,
            col1_width,
            body_font,
            body_size,
            line_height,
        )
        tip_y = draw_wrapped_block(
            c,
            tip_text,
            table_x + col1_width + col_gap,
            row_top,
            col2_width,
            body_font,
            body_size,
            line_height,
        )
        row_bottom = min(scene_y, tip_y)
        c.line(table_x, row_bottom + 4, table_x + table_width, row_bottom + 4)
        y_row = row_bottom - line_height

    summary_y_start = y_row - line_height
    draw_wrapped_block(
        c,
        footer_text,
        table_x,
        summary_y_start,
        table_width,
        body_font,
        body_size,
        line_height,
    )

    draw_page_number(c, 7)
    c.showPage()


# ------------------------------------------------------------------
# 第 8 页：まとめ 用の文面生成（变量版）
# ------------------------------------------------------------------
def build_page8_summary(male_name: str, female_name: str, compat_score: int) -> str:
    """
    之后你可以把这里换成「要素组合→まとめ模板」。
    现在先给一个柔らかいデフォルト。
    目标：大约 230〜260 字，8〜10 行。
    """
    return (
        f"{male_name} さんと {female_name} さんのホロスコープからは、"
        "ふたりが出会ったこと自体に、やわらかな意味合いが感じられます。"
        "価値観やペースの違いはありながらも、安心できるところと刺激になるところが、"
        "ちょうどよく混ざり合っている組み合わせです。"
        "大切なのは、どちらか一方の正解に寄せるのではなく、"
        "ふたりだけのちょうどいい距離感や歩幅を、少しずつ探していくことです。"
        "このレポートで気になったポイントがあれば、小さな会话のきっかけとして、"
        "「実はこう感じていたんだ」と伝えてみてください。"
        "星の配置は、完璧なかたちを決めつけるものではなく、"
        "ふたりがこれから選んでいく物語を、そっと照らしてくれるヒントです。"
    )


# ==============================================================
#                    生成 PDF 主入口
# ==============================================================

SIGNS_JA = [
    "牡羊座", "牡牛座", "双子座", "蟹座", "獅子座", "乙女座",
    "天秤座", "蠍座", "射手座", "山羊座", "水瓶座", "魚座",
]


def _deg_and_sign(seed: int, mul: int, offset: int):
    """简单的伪星盘：用生日+时间算一个稳定的度数和星座（不是天文学真星盘，只是应急上线用）"""
    deg = (seed * mul + offset) % 360
    idx = int(deg // 30) % 12
    return deg, SIGNS_JA[idx]

# ----------------------------------------------------
# 简单星座计算：只返回“太阳/月亮/上升/金星/火星”所属星座
# ----------------------------------------------------
def compute_simple_signs(birth_date, birth_time):
    """
    输入：生日（YYYY-MM-DD）、时间（HH:MM）
    输出：五个星体的星座（不计算度数，不需要外部API）
    """

    # 解析生日
    try:
        y, m, d = [int(x) for x in birth_date.split("-")]
    except:
        y, m, d = 1990, 1, 1

    # 解析时间
    try:
        hh, mm = [int(x) for x in birth_time.split(":")]
    except:
        hh, mm = 12, 0

    # 生成一个简单种子，用于星座分配（保持同一天的人固定结果）
    seed = (y * 1231 + m * 97 + d * 13 + hh * 7 + mm) % 360

    def get_sign(offset):
        idx = ((seed + offset) % 360) // 30
        return SIGNS_JA[int(idx)]

    return {
        "sun": get_sign(0),
        "moon": get_sign(40),
        "asc": get_sign(80),
        "venus": get_sign(160),
        "mars": get_sign(220),
    }


# 12星座英文 → 日文
SIGN_JA = {
    "ARI": "牡羊座",
    "TAU": "牡牛座",
    "GEM": "双子座",
    "CAN": "蟹座",
    "LEO": "獅子座",
    "VIR": "乙女座",
    "LIB": "天秤座",
    "SCO": "蠍座",
    "SAG": "射手座",
    "CAP": "山羊座",
    "AQU": "水瓶座",
    "PIS": "魚座",
}

def compute_core_from_birth(birth_date, birth_time, birth_place):
    """
    入口函数：根据出生信息，返回 5 个星体的“星座名字”。

    现在走的是【简化版：只算星座，不算真实度数】，调用 compute_simple_signs。
    以后如果要接真实星盘 API，只要改这个函数，把返回结果保持同样结构即可。
    """
    return compute_simple_signs(birth_date, birth_time)


@app.route("/api/generate_report", methods=["GET"])
def generate_report():
    # ---- 1. 读取参数 ----
    # 名字：不再给「太郎 / 花子」默认值，如果取不到就变成空字符串
    male_name = (
        request.args.get("male_name")
        or request.args.get("your_name")
        or request.args.get("name")
        or ""
    )
    female_name = (
        request.args.get("female_name")
        or request.args.get("partner_name")
        or request.args.get("partner")
        or ""
    )

    raw_date = request.args.get("date")
    date_display = get_display_date(raw_date)

    # 生日 / 时间 / 地点：先尝试多种 key，实在没有才用默认
    your_dob = (
        request.args.get("your_dob")
        or request.args.get("male_dob")
        or request.args.get("dob")
        or "1990-01-01"
    )
    your_time = (
        request.args.get("your_time")
        or request.args.get("male_time")
        or "12:00"
    )
    your_place = (
        request.args.get("your_place")
        or request.args.get("male_place")
        or "Tokyo"
    )

    partner_dob = (
        request.args.get("partner_dob")
        or request.args.get("female_dob")
        or request.args.get("partner_dob")
        or "1990-01-01"
    )
    partner_time = (
        request.args.get("partner_time")
        or request.args.get("female_time")
        or "12:00"
    )
    partner_place = (
        request.args.get("partner_place")
        or request.args.get("female_place")
        or "Tokyo"
    )

    # ---- 2. 计算双方核心星盘（现在是简易伪星盘）----
    male_core = compute_core_from_birth(your_dob, your_time, your_place)
    female_core = compute_core_from_birth(partner_dob, partner_time, partner_place)

    # ---- 3. 准备 PDF 缓冲区 ----
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # ------------------------------------------------------------------
    # PAGE 1：封面
    # ------------------------------------------------------------------
    draw_full_bg(c, "cover.jpg")

    c.setFont(JP_SANS, 18)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    couple_text = f"{male_name} さん ＆ {female_name} さん"
    c.drawCentredString(PAGE_WIDTH / 2, 420, couple_text)

    c.setFont(JP_SANS, 12)
    date_text = f"作成日：{date_display}"
    c.drawCentredString(PAGE_WIDTH / 2, 80, date_text)

    c.showPage()

    # ------------------------------------------------------------------
    # PAGE 2：このレポートについて（背景固定，不生成内容）
    # ------------------------------------------------------------------
    draw_full_bg(c, "index.jpg")
    c.showPage()

    # ------------------------------------------------------------------
    # PAGE 3：基本ホロスコープと総合相性（完全变量版）
    # ------------------------------------------------------------------
    compat_score, compat_summary, sun_text, moon_text, asc_text = build_page3_texts(
        male_name, female_name, male_core, female_core
    )

    draw_page3_basic_and_synastry(
        c,
        male_name,
        female_name,
        male_core,
        female_core,
        compat_score,
        compat_summary,
        sun_text,
        moon_text,
        asc_text,
    )

    # ------------------------------------------------------------------
    # PAGE 4：性格の違いとコミュニケーション（变量文本生成）
    # ------------------------------------------------------------------
    def build_page4_texts(male_name, female_name, male_core, female_core):
        talk_text = (
            f"{male_name} さんは、自分の気持ちを言葉にするまでに少し時間をかける、じっくりタイプです。"
            f"一方で、{female_name} さんは、その場で感じたことをすぐに言葉にする、テンポの速いタイプです。"
            "日常会話では、片方が考えている間にもう一方がどんどん話してしまい、"
            "「ちゃんと聞いてもらえていない」と感じる場面が出やすくなります。"
        )
        talk_summary = (
            "一言でいうと、二人の話し方は「スピードの違いを理解し合うことで心地よくつながれるペア」です。"
        )
        problem_text = (
            f"{male_name} さんは、問題が起きたときにまず全体を整理してから、落ち着いて対処しようとします。"
            f"{female_name} さんは、感情の動きに敏感で、まず気持ちを共有したいタイプです。"
            "同じ出来事でも、片方は「どう解決するか」、もう片方は「どう感じたか」を大事にするため、"
            "タイミングがずれると、すれ違いが生まれやすくなります。"
        )
        problem_summary = (
            "一言でいうと、二人は「解決志向」と「共感志向」が支え合う、心強いバランス型のペアです。"
        )
        values_text = (
            f"{male_name} さんは、安定や責任感を重視する一方で、{female_name} さんは、変化やワクワク感を大切にする傾向があります。"
            "お金の使い方や休日の過ごし方、将来のイメージなど、小さな違いが積み重なると、"
            "「なんでわかってくれないの？」と感じる瞬間が出てくるかもしれません。"
        )
        values_summary = (
            "一言でいうと、二人の価値観は違いを否定するのではなく、「お互いの世界を広げ合うきっかけ」になる組み合わせです。"
        )
        return (
            talk_text, talk_summary,
            problem_text, problem_summary,
            values_text, values_summary,
        )

    (
        talk_text, talk_summary,
        problem_text, problem_summary,
        values_text, values_summary,
    ) = build_page4_texts(male_name, female_name, male_core, female_core)

    draw_page4_communication(
        c,
        talk_text, talk_summary,
        problem_text, problem_summary,
        values_text, values_summary,
    )

    # ------------------------------------------------------------------
    # PAGE 5：相性の良い点・すれ違いやすい点（变量文本生成）
    # ------------------------------------------------------------------
    def build_page5_texts(male_name, female_name, male_core, female_core):
        good_text = (
            f"{male_name} さんは、相手の立場を考えながら行動できる、落ち着いた安心感のあるタイプです。"
            f"{female_name} さんは、その場の空気を明るくし、素直な気持ちを伝えられるタイプです。"
            "二人が一緒にいると、「安心感」と「温かさ」が自然と周りにも伝わり、"
            "お互いの長所を引き出し合える関係になりやすい組み合わせです。"
        )
        good_summary = (
            "一言でいうと、二人は「一緒にいるだけで場がやわらぎ、温かさが自然と伝わっていくペア」です。"
        )
        gap_text = (
            f"{male_name} さんは、物事を決めるときに慎重に考えたいタイプで、"
            f"{female_name} さんは、流れや直感を大切にして「とりあえずやってみよう」と思うことが多いかもしれません。"
            "そのため、決断のペースや優先順位がずれると、"
            "「どうしてそんなに急ぐの？」「どうしてそんなに慎重なの？」とお互いに感じやすくなります。"
        )
        gap_summary = (
            "一言でいうと、二人のすれ違いは「慎重さ」と「フットワークの軽さ」の差ですが、そのギャップは視野を広げるヒントにもなります。"
        )
        hint_text = (
            f"{male_name} さんの安定感と、{female_name} さんの柔軟さ・明るさが合わさることで、"
            "二人は「現実的で無理のないチャレンジ」を積み重ねていけるペアです。"
            "お互いの考え方を一度言葉にして共有する習慣ができると、"
            "二人だけのペースや目標が見つかり、将来像もより具体的に描きやすくなります。"
        )
        hint_summary = (
            "一言でいうと、二人の伸ばしていけるポイントは「安心できる土台の上で、新しい一歩を一緒に踏み出せる力」です。"
        )
        return (
            good_text, good_summary,
            gap_text, gap_summary,
            hint_text, hint_summary,
        )

    (
        good_text, good_summary,
        gap_text, gap_summary,
        hint_text, hint_summary,
    ) = build_page5_texts(male_name, female_name, male_core, female_core)

    draw_page5_points(
        c,
        good_text, good_summary,
        gap_text, gap_summary,
        hint_text, hint_summary,
    )

    # ------------------------------------------------------------------
    # PAGE 6：関係の方向性と今後の傾向（变量文本生成）
    # ------------------------------------------------------------------
    def build_page6_texts(male_name, female_name, male_core, female_core):
        theme_text = (
            "二人の関係は、「安心感」と「前進力」をバランスよく両立させていくタイプです。"
            "大切にしたい価値観や向かう方向が似ているため、土台が安定しやすく、"
            "意見が分かれる場面でも最終的には同じゴールを選びやすいペアです。"
        )
        theme_summary = (
            "一言でいうと、「同じ方向を見て進める安定感のあるテーマ」です。"
        )
        emotion_text = (
            "感情の深まり方は、最初はゆっくりですが、一度安心できると一気に距離が縮まるスタイルです。"
            "相手の気持ちを丁寧に受け取るほど信頼が積み重なり、"
            "日常の小さな会話から親密さが育っていきます。"
        )
        emotion_summary = (
            "一言でいうと、「ゆっくり始まり、深くつながる流れ」です。"
        )
        style_text = (
            "このペアは、片方が雰囲気をつくり、もう片方が行動を整えるように、"
            "自然と役割分担が生まれやすい組み合わせです。"
            "生活のペースと会话のリズムが合いやすく、無理なく居心地の良い関係を形にできます。"
        )
        style_summary = (
            "一言でいうと、「調和しながら一緒に形を作る関係」です。"
        )
        future_text = (
            "今後1〜2年は、安心できる土台の上で少しずつ新しい挑戦を重ねていく時期です。"
            "環境の変化にも協力して向き合うことで、関係の方向性がよりはっきりしていきます。"
        )
        future_summary = (
            "一言でいうと、「安定の中で小さな前進が続く時期」です。"
        )
        return (
            theme_text, theme_summary,
            emotion_text, emotion_summary,
            style_text, style_summary,
            future_text, future_summary,
        )

    (
        theme_text, theme_summary,
        emotion_text, emotion_summary,
        style_text, style_summary,
        future_text, future_summary,
    ) = build_page6_texts(male_name, female_name, male_core, female_core)

    draw_page6_trend(
        c,
        theme_text, theme_summary,
        emotion_text, emotion_summary,
        style_text, style_summary,
        future_text, future_summary,
    )

    # ------------------------------------------------------------------
    # PAGE 7：日常で役立つアドバイス（变量文本生成）
    # ------------------------------------------------------------------
    def build_page7_texts(male_name, female_name, male_core, female_core):
        advice_rows = [
            (
                "忙しい平日の夜",
                "10分だけ携帯を置いて、お互いに「今日いちばん嬉しかったこと」を一つずつ話してみましょう。"
            ),
            (
                "休みの日のデート前",
                "予定を決める前に「今日はどんな気分？」と聞くひと言だけで、行き先のすれ違いが減りやすくなります。"
            ),
            (
                "気持ちがすれ違ったとき",
                "どちらが正しいかよりも、「今どう感じた？」を先に听くと、落ち着いて话し直しやすくなります。"
            ),
            (
                "記念日や特別な日",
                "完璧を目指しすぎず、「お互いに一つずつ感謝を伝える」くらいのシンプルさが、ちょうどいいバランスです。"
            ),
            (
                "相手が疲れていそうな日",
                "アドバイスよりも「今日はおつかれさま」と一言ねぎらうだけで、安心感がぐっと高まります。"
            ),
            (
                "なんとなく距離を感じるとき",
                "重い話ではなく、「最近ハマっていること教えて？」など、軽いテーマから会話をつなげてみましょう。"
            ),
        ]
        footer_text = (
            "ここに挙げたのはあくまで一例です。"
            "ふたりらしい言葉やタイミングにアレンジしながら、"
            "日常の中で少しずつ「話すきっかけ」を増やしていってください。"
        )
        return advice_rows, footer_text

    advice_rows, footer_text = build_page7_texts(male_name, female_name, male_core, female_core)

    draw_page7_advice(c, advice_rows, footer_text)

    # ------------------------------------------------------------------
    # PAGE 8：まとめ（变量版）
    # ------------------------------------------------------------------
    draw_full_bg(c, "page_summary.jpg")
    c.setFillColorRGB(0.2, 0.2, 0.2)

    summary_x = 120
    summary_y = 680
    summary_wrap_width = 350
    summary_font = JP_SERIF
    summary_font_size = 13
    summary_line_height = 20

    summary_text = build_page8_summary(male_name, female_name, compat_score)

    draw_wrapped_block(
        c,
        summary_text,
        summary_x,
        summary_y,
        summary_wrap_width,
        summary_font,
        summary_font_size,
        summary_line_height,
    )

    c.showPage()

    # ------------------------------------------------------------------
    # 收尾：保存并返回 PDF
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
# Tally webhook（示例）：接收表单 JSON
# ------------------------------------------------------------------
@app.route("/tally_webhook", methods=["POST"])
def tally_webhook():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    print("Tally webhook payload:", data)
    return {"status": "ok"}


# ------------------------------------------------------------------
# 主程序入口
# ------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

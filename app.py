import io
import os
from datetime import datetime

from flask import Flask, send_file, request
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# -------------------------------------------------
# Flask 基本设置
# -------------------------------------------------
# static_folder 指向 public，方便直接访问 /assets/xx
app = Flask(__name__, static_url_path='', static_folder='public')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
ASSETS_DIR = os.path.join(PUBLIC_DIR, "assets")

PAGE_WIDTH, PAGE_HEIGHT = A4  # (595.27, 841.89)

# -------------------------------------------------
# 字体注册（注意：这里用的是 .ttf 版本）
# -------------------------------------------------
def register_fonts():
    try:
        pdfmetrics.registerFont(
            TTFont("NotoSansJP-Regular",
                   os.path.join(ASSETS_DIR, "NotoSansJP-Regular.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont("NotoSansJP-Medium",
                   os.path.join(ASSETS_DIR, "NotoSansJP-Medium.ttf"))
        )
        pdfmetrics.registerFont(
            TTFont("NotoSansJP-Bold",
                   os.path.join(ASSETS_DIR, "NotoSansJP-Bold.ttf"))
        )
        print("Japanese fonts registered successfully.")
    except Exception as e:
        # 注册失败时至少打印出来，方便在 Render 日志里看到
        print("Font register error:", e)


register_fonts()

# -------------------------------------------------
# 小工具：加载背景图
# -------------------------------------------------
def draw_full_background(c, filename):
    """把指定图片铺满整页"""
    path = os.path.join(ASSETS_DIR, filename)
    if os.path.exists(path):
        c.drawImage(
            path,
            0,
            0,
            width=PAGE_WIDTH,
            height=PAGE_HEIGHT,
            preserveAspectRatio=True,
            mask='auto'
        )
    else:
        print(f"[warn] background not found: {path}")


# -------------------------------------------------
# 小工具：日期格式转换
#   入参： 2025-01-01 / 2025/01/01 / 2025.01.01 之类
#   出参： 2025年01月01日
# -------------------------------------------------
def format_date_jp(date_str):
    if not date_str:
        return "作成日："
    # 统一分隔符
    s = date_str.replace(".", "-").replace("/", "-")
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return f"作成日：{dt.year}年{dt.month:02d}月{dt.day:02d}日"
    except ValueError:
        # 解析不了就直接原样拼上去，至少不会挂
        return f"作成日：{date_str}"


# -------------------------------------------------
# 各页绘制
# -------------------------------------------------
def draw_cover_page(c, male_name, female_name, created_date_str):
    """封面：只用背景自带的标题，只额外加姓名 + 作成日"""
    draw_full_background(c, "cover.jpg")

    # 姓名行：太郎 さん ＆ 花子 さん
    names_text = f"{male_name} さん ＆ {female_name} さん"
    c.setFont("NotoSansJP-Medium", 18)
    # 横向居中，纵向放在「恋愛占星レポート」稍上方
    c.drawCentredString(PAGE_WIDTH / 2, 520, names_text)

    # 作成日：YYYY年MM月DD日 （放在背景预留的底部位置）
    c.setFont("NotoSansJP-Regular", 12)
    c.drawCentredString(PAGE_WIDTH / 2, 105, created_date_str)

    c.showPage()


def draw_intro_page(c):
    """第 2 页：简单说明（背景自带标题，只画正文）"""
    draw_full_background(c, "index.jpg")

    c.setFont("NotoSansJP-Bold", 18)
    c.drawString(70, 720, "日本語フォントのクリーンテスト")

    c.setFont("NotoSansJP-Regular", 12)
    text = (
        "このPDFに黒い四角の記号が見えなければ、フォントの設定は問題ありません。\n"
        "漢字・ひらがな・カタカナだけが表示されているかをご確認ください。"
    )
    text_obj = c.beginText(70, 690)
    text_obj.setLeading(18)
    for line in text.split("\n"):
        text_obj.textLine(line)
    c.drawText(text_obj)

    c.showPage()


def draw_basic_horoscope_page(c, male_name, female_name):
    """基本ホロスコープ + 2人の星盤（左右）"""
    draw_full_background(c, "page_basic.jpg")

    # 星盤基底图
    chart_path = os.path.join(ASSETS_DIR, "chart_base.png")

    chart_size = 260  # 星盘直径
    # 左右居中放在白色区域内（粗略调过，大致不会超出去）
    left_x = 70
    right_x = PAGE_WIDTH - 70 - chart_size
    chart_y = 280

    if os.path.exists(chart_path):
        # 左：男性
        c.drawImage(
            chart_path,
            left_x,
            chart_y,
            width=chart_size,
            height=chart_size,
            preserveAspectRatio=True,
            mask='auto'
        )
        # 右：女性
        c.drawImage(
            chart_path,
            right_x,
            chart_y,
            width=chart_size,
            height=chart_size,
            preserveAspectRatio=True,
            mask='auto'
        )
    else:
        print(f"[warn] chart image not found: {chart_path}")

    # 星盘下姓名标签
    c.setFont("NotoSansJP-Medium", 14)
    c.drawCentredString(left_x + chart_size / 2, chart_y - 20, f"{male_name} さん")
    c.drawCentredString(right_x + chart_size / 2, chart_y - 20, f"{female_name} さん")

    # 下方注意说明
    c.setFont("NotoSansJP-Regular", 10)
    note = "※ 今は星の位置はまだ固定イラストです。後で自動計算を組み込みます。"
    c.drawString(80, 120, note)

    c.showPage()


def draw_communication_page(c):
    """性格の違いとコミュニケーション"""
    draw_full_background(c, "page_communication.jpg")

    c.setFont("NotoSansJP-Regular", 12)
    text = (
        "話し方やテンポの違いは、ケンカの火種になることもあれば、\n"
        "お互いを補い合う魅力になることもあります。\n\n"
        "このページには、会話のスタイルや気持ちの伝え方に関するアドバイスが入ります。（デモ）"
    )
    txt = c.beginText(70, 640)
    txt.setLeading(18)
    for line in text.split("\n"):
        txt.textLine(line)
    c.drawText(txt)

    c.showPage()


def draw_points_page(c):
    """相性の良い点・すれ違いやすい点"""
    draw_full_background(c, "page_points.jpg")

    c.setFont("NotoSansJP-Regular", 12)
    text = (
        "ここには、おふたりの相性の良い点と、すれ違いやすいポイントに関する文章が入ります。（デモ）\n\n"
        "・相性の良いところ\n"
        "・すれ違いやすいところ\n"
        "・関係をスムーズにするヒント"
    )
    txt = c.beginText(70, 650)
    txt.setLeading(18)
    for line in text.split("\n"):
        txt.textLine(line)
    c.drawText(txt)

    c.showPage()


def draw_trend_page(c):
    """関係の方向性と今後の傾向"""
    draw_full_background(c, "page_trend.jpg")

    c.setFont("NotoSansJP-Regular", 12)
    text = (
        "このページには、今の関係ステージや今後の流れに関する文章が入ります。（デモ）\n\n"
        "出会い期・成長期・安定期など、関係のリズムを知ることで、\n"
        "無理をせずに距離感を調整しやすくなります。"
    )
    txt = c.beginText(70, 640)
    txt.setLeading(18)
    for line in text.split("\n"):
        txt.textLine(line)
    c.drawText(txt)

    c.showPage()


def draw_advice_page(c):
    """日常で役立つアドバイス"""
    draw_full_background(c, "page_advice.jpg")

    c.setFont("NotoSansJP-Regular", 12)
    text = (
        "ここには、日常生活で使える具体的なアドバイスが入ります。（デモ）\n\n"
        "・ケンカになりそうなときのクールダウン方法\n"
        "・相手に「ありがとう」を伝えるタイミング\n"
        "・忙しいときでも心の距離を保つコツ"
    )
    txt = c.beginText(70, 640)
    txt.setLeading(18)
    for line in text.split("\n"):
        txt.textLine(line)
    c.drawText(txt)

    c.showPage()


def draw_summary_page(c):
    """まとめ"""
    draw_full_background(c, "page_summary.jpg")

    c.setFont("NotoSansJP-Bold", 16)
    c.drawString(70, 690, "まとめ（サンプル）")

    c.setFont("NotoSansJP-Regular", 12)
    text = (
        "本レポートは、テンプレートとフォントの動作確認用デモです。\n"
        "星の計算ロジックと個別の文章生成は、このあと段階的に組み込んでいきます。\n\n"
        "占いの結果は運命を決めるものではなく、\n"
        "おふたりがより深く理解し合い、\n"
        "穏やかで優しい気持ちで愛を育むための小さな指針です。"
    )
    txt = c.beginText(70, 660)
    txt.setLeading(18)
    for line in text.split("\n"):
        txt.textLine(line)
    c.drawText(txt)

    c.showPage()


# -------------------------------------------------
# Flask ルート
# -------------------------------------------------
@app.route("/")
def root():
    return "PDF server running."


@app.route("/test.html")
def test_page():
    return app.send_static_file("test.html")


@app.route("/api/generate_report", methods=["GET"])
def generate_report():
    """
    例：
    /api/generate_report?male_name=太郎&female_name=花子&date=2025-01-01
    """
    male_name = request.args.get("male_name", "太郎")
    female_name = request.args.get("female_name", "花子")
    date_str = request.args.get("date", "")  # 允许空
    created_date_jp = format_date_jp(date_str)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # 顺序：封面 -> 说明页 -> 星盘 -> 其余页面
    draw_cover_page(c, male_name, female_name, created_date_jp)
    draw_intro_page(c)
    draw_basic_horoscope_page(c, male_name, female_name)
    draw_communication_page(c)
    draw_points_page(c)
    draw_trend_page(c)
    draw_advice_page(c)
    draw_summary_page(c)

    c.save()
    buffer.seek(0)

    filename = f"love_report_{male_name}_{female_name}.pdf"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )


# -------------------------------------------------
# 本地调试用（Render 上不会走这里）
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

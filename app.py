from flask import Flask, send_file, request
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io

app = Flask(__name__, static_url_path='', static_folder='public')

# ---- 根路径，防止 Render 显示 404 ----
@app.route('/')
def root():
    return "PDF server running."

# ---- 静态文件 test.html 依然可以访问 ----
@app.route('/test.html')
def test_page():
    return app.send_static_file('test.html')

# ---- 生成 PDF（最小测试版） ----
@app.route('/api/generate_report', methods=['GET'])
def generate_pdf():
    buffer = io.BytesIO()

    # 创建 PDF（A4 竖版）
    p = canvas.Canvas(buffer, pagesize=A4)

    # 测试写一段文字
    p.setFont("Helvetica", 20)
    p.drawString(100, 800, "PDF 生成成功！")

    # 结束页面
    p.showPage()
    p.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="test.pdf",
        mimetype='application/pdf'
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)

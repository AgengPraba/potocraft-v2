from flask import Flask, render_template, request, send_from_directory, jsonify
from rembg import remove
from PIL import Image
import os
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pasfoto')
def pasfoto():
    return render_template('pasfoto.html')

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['photo']
    filename = f"{uuid.uuid4().hex}.png"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    return jsonify({"filename": filename})

@app.route('/crop', methods=['POST'])
def crop():
    file = request.files['cropped']
    filename = f"{uuid.uuid4().hex}_cropped.png"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    return jsonify({"filename": filename, "cropped_path": f"/{path}"})

@app.route('/remove_bg', methods=['POST'])
def remove_bg():
    data = request.json
    filename = data['filename']
    bg_color = data['bgColor']
    input_path = os.path.join(UPLOAD_FOLDER, filename)

    with Image.open(input_path) as img:
        no_bg = remove(img)

        # Tambahkan background baru
        bg = Image.new("RGBA", no_bg.size, bg_color)
        combined = Image.alpha_composite(bg, no_bg.convert("RGBA"))

        new_name = f"{uuid.uuid4().hex}_nobg.png"
        output_path = os.path.join(UPLOAD_FOLDER, new_name)
        combined.save(output_path)

    return jsonify({"processed_path": f"/{output_path}", "filename": new_name})

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)

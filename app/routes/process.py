from flask import Blueprint, request, jsonify, current_app, send_from_directory
from PIL import Image
from rembg import remove
import uuid
import os

process_bp = Blueprint('process', __name__)

@process_bp.route('/upload', methods=['POST'])
def upload():
    file = request.files['photo']
    filename = f"{uuid.uuid4().hex}.png"
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    return jsonify({"filename": filename})

@process_bp.route('/crop', methods=['POST'])
def crop():
    file = request.files['cropped']
    filename = f"{uuid.uuid4().hex}_cropped.png"
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    return jsonify({"filename": filename, "cropped_path": f"/{path}"})

@process_bp.route('/remove_bg', methods=['POST'])
def remove_bg():
    data = request.json
    filename = data['filename']
    bg_color = data['bgColor']
    input_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

    with Image.open(input_path) as img:
        no_bg = remove(img)
        bg = Image.new("RGBA", no_bg.size, bg_color)
        combined = Image.alpha_composite(bg, no_bg.convert("RGBA"))

        new_name = f"{uuid.uuid4().hex}_nobg.png"
        output_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_name)
        combined.save(output_path)

    return jsonify({"processed_path": f"/{output_path}", "filename": new_name})

@process_bp.route('/download/<filename>')
def download(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

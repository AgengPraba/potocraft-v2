# app/routes/process.py
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from PIL import Image, ImageEnhance # ImageEnhance untuk kecerahan jika diperlukan nanti
from rembg import remove
import uuid
import os

process_bp = Blueprint('process', __name__)

# Helper untuk memastikan nama file aman (opsional tapi bagus)
def secure_filename_custom(filename):
    # Implementasi sederhana, bisa diganti dengan werkzeug.utils.secure_filename jika diinginkan
    return "".join(c for c in filename if c.isalnum() or c in ('.', '_', '-')).strip()

@process_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'photo' not in request.files:
        return jsonify({"error": "Tidak ada file foto yang diupload"}), 400
    
    file = request.files['photo']
    
    if file.filename == '':
        return jsonify({"error": "Nama file kosong"}), 400

    if file:
        # Menggunakan ekstensi asli atau default ke .png
        original_filename, original_extension = os.path.splitext(file.filename)
        safe_original_filename = secure_filename_custom(original_filename)
        extension = original_extension if original_extension else '.png'
        
        filename = f"{uuid.uuid4().hex}_{safe_original_filename}{extension}"
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        try:
            file.save(upload_path)
            current_app.logger.info(f"File '{filename}' berhasil diupload ke '{upload_path}'")
            return jsonify({
                "message": "Upload berhasil",
                "filename": filename,
                "url": f"/static/uploads/{filename}" # Path untuk diakses dari frontend
            }), 200
        except Exception as e:
            current_app.logger.error(f"Gagal menyimpan file: {e}")
            return jsonify({"error": f"Gagal menyimpan file: {str(e)}"}), 500
    
    return jsonify({"error": "File tidak valid"}), 400


@process_bp.route('/crop', methods=['POST'])
def crop_image():
    if 'cropped' not in request.files:
        return jsonify({'error': 'Tidak ada data gambar yang di-crop'}), 400

    brightness = float(request.form.get('brightness', 1.0)) # Terima nilai kecerahan, default 1.0

    cropped_file = request.files['cropped']
    original_filename = request.form.get('original_filename') # Kita perlu mengirim ini dari frontend

    if cropped_file and original_filename:
        try:
            img = Image.open(cropped_file)
            # Aplikasikan kecerahan
            enhancer = ImageEnhance.Brightness(img)
            img_brightened = enhancer.enhance(brightness)

            original_name, ext = os.path.splitext(secure_filename_custom(original_filename))
            cropped_unique_filename = f"{uuid.uuid4().hex}_{original_name}_cropped_brightened{ext}"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], cropped_unique_filename)
            img_brightened.save(save_path)
            current_app.logger.info(f"File '{cropped_unique_filename}' disimpan.")
            return jsonify({'filename': cropped_unique_filename, 'url': f"/static/uploads/{cropped_unique_filename}"}), 200
        except Exception as e:
            current_app.logger.error(f"Error saat crop dan mengubah kecerahan: {e}")
            return jsonify({'error': f'Gagal memproses crop: {str(e)}'}), 500
    return jsonify({'error': 'File crop atau nama file asli tidak valid'}), 400


@process_bp.route('/remove_bg', methods=['POST'])
def remove_background_api():
    data = request.json
    if not data or 'filename' not in data or 'bgColor' not in data:
        return jsonify({"error": "Data tidak lengkap (filename atau bgColor tidak ada)"}), 400

    filename = data['filename']
    bg_color_hex = data['bgColor'] # contoh: "#FF0000"

    input_path = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename_custom(filename))

    if not os.path.exists(input_path):
        return jsonify({"error": f"File '{filename}' tidak ditemukan."}), 404

    try:
        with Image.open(input_path) as img:
            # Hapus background menggunakan rembg
            img_no_bg = remove(img) # Hasilnya adalah RGBA dengan background transparan

            # Buat background baru dengan warna yang dipilih
            # Konversi warna hex ke tuple RGB
            bg_color_hex = bg_color_hex.lstrip('#')
            bg_color_rgb = tuple(int(bg_color_hex[i:i+2], 16) for i in (0, 2, 4))
            
            # Buat gambar background dengan warna solid dan ukuran yang sama
            # Pastikan background punya alpha channel jika akan di-composite dengan gambar RGBA
            background_img = Image.new("RGBA", img_no_bg.size, (*bg_color_rgb, 255))
            
            # Gabungkan gambar tanpa background di atas gambar background berwarna
            # Pastikan img_no_bg dalam mode RGBA untuk alpha_composite
            final_image = Image.alpha_composite(background_img, img_no_bg.convert("RGBA"))

        original_name, _ = os.path.splitext(filename)
        safe_original_name = secure_filename_custom(original_name)
        new_filename = f"{uuid.uuid4().hex}_{safe_original_name}_bgremoved.png"
        output_path = os.path.join(current_app.config['UPLOAD_FOLDER'], new_filename)
        
        final_image.save(output_path, 'PNG')
        current_app.logger.info(f"File dengan background baru '{new_filename}' disimpan.")
        return jsonify({
            "message": "Background berhasil diproses",
            "filename": new_filename,
            "url": f"/static/uploads/{new_filename}"
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error saat remove background: {e}")
        return jsonify({"error": f"Gagal memproses background: {str(e)}"}), 500

@process_bp.route('/apply_outfit', methods=['POST'])
def apply_outfit_api():
    data = request.json
    if not data or 'base_image_filename' not in data or 'outfit_id' not in data:
        return jsonify({"error": "Data tidak lengkap"}), 400

    base_image_filename = secure_filename_custom(data['base_image_filename'])
    outfit_id = secure_filename_custom(data['outfit_id']) # misal "jas1", "jas2"

    base_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], base_image_filename)
    outfit_image_path = os.path.join(current_app.static_folder, 'outfits', f"{outfit_id}.png")

    if not os.path.exists(base_image_path):
        return jsonify({"error": "Gambar dasar tidak ditemukan"}), 404
    if not os.path.exists(outfit_image_path):
        return jsonify({"error": f"Gambar outfit '{outfit_id}.png' tidak ditemukan"}), 404

    try:
        img_base = Image.open(base_image_path).convert("RGBA")
        img_outfit = Image.open(outfit_image_path).convert("RGBA")

        # --- Logika Penempatan Outfit Sederhana ---
        # Ini adalah contoh yang sangat dasar. Anda PERLU menyesuaikannya secara signifikan
        # untuk hasil yang baik, mungkin dengan deteksi wajah/bahu (OpenCV/Mediapipe).

        # Contoh: Skala outfit agar lebarnya 80% dari gambar dasar
        outfit_target_width = int(img_base.width * 0.8) # 80% lebar gambar dasar
        outfit_ratio = outfit_target_width / img_outfit.width
        outfit_target_height = int(img_outfit.height * outfit_ratio)
        img_outfit_resized = img_outfit.resize((outfit_target_width, outfit_target_height), Image.Resampling.LANCZOS)
        
        # Posisi penempelan (contoh: tengah secara horizontal, dan sedikit ke bawah dari atas)
        # Anda harus sangat menyesuaikan ini!
        x_offset = (img_base.width - img_outfit_resized.width) // 2
        
        # y_offset ini sangat spekulatif. Pas foto biasanya fokus pada wajah & bahu.
        # Misal, asumsikan outfit mulai sekitar 30% dari atas gambar.
        y_offset_percentage_from_top = 0.30 
        y_offset = int(img_base.height * y_offset_percentage_from_top)
        
        # Pastikan area tempel tidak negatif
        paste_position = (max(0, x_offset), max(0, y_offset))

        # Buat canvas baru untuk komposisi
        composited_image = Image.new("RGBA", img_base.size)
        composited_image.paste(img_base, (0,0)) # Tempel gambar dasar dulu
        # Tempel outfit di atasnya, menggunakan alpha mask dari outfit itu sendiri
        composited_image.paste(img_outfit_resized, paste_position, img_outfit_resized)

        original_name, _ = os.path.splitext(base_image_filename)
        safe_original_name = secure_filename_custom(original_name)
        final_image_filename = f"{uuid.uuid4().hex}_{safe_original_name}_outfit_{outfit_id}.png"
        final_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], final_image_filename)
        composited_image.save(final_image_path, 'PNG')
        current_app.logger.info(f"File dengan outfit '{final_image_filename}' disimpan.")
        return jsonify({
            "message": "Outfit berhasil diterapkan",
            "filename": final_image_filename,
            "url": f"/static/uploads/{final_image_filename}"
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error saat menerapkan outfit: {str(e)}")
        return jsonify({"error": f"Gagal menerapkan outfit: {str(e)}"}), 500

@process_bp.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
#============================ fitur selain pas foto

@process_bp.route('/process-remove-background', methods=['POST'])
def process_remove_background():
    if 'image' not in request.files:
        return jsonify({'error': 'Tidak ada file gambar'}), 400
    
    file = request.files['image']
    bg_color_hex = request.form.get('bgColor', '') # Bisa string kosong untuk transparan

    if file.filename == '':
        return jsonify({'error': 'Nama file kosong'}), 400

    # --- AWAL LOGIKA PEMROSESAN (CONTOH DUMMY) ---
    # Di sini Anda akan menggunakan 'rembg' dan Pillow seperti di fungsi remove_background_api Anda
    # Untuk sekarang, kita hanya simpan file asli dan kembalikan pathnya
    try:
        filename = secure_filename_custom(file.filename) # Gunakan fungsi Anda
        unique_filename = f"removedbg_{uuid.uuid4().hex}_{filename}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(save_path) # Simpan file asli (atau hasil proses rembg)
        
        current_app.logger.info(f"Proses Hapus BG (dummy) untuk '{file.filename}', warna: '{bg_color_hex}'. Disimpan sebagai {unique_filename}")

        # Simulasi hasil dengan background (atau transparan)
        # Ganti ini dengan URL file yang benar-benar sudah diproses
        processed_url = f"/static/uploads/{unique_filename}" 

        return jsonify({'url': processed_url, 'filename': unique_filename})
    except Exception as e:
        current_app.logger.error(f"Error dummy process_remove_background: {e}")
        return jsonify({'error': str(e)}), 500
    # --- AKHIR LOGIKA PEMROSESAN (CONTOH DUMMY) ---

@process_bp.route('/process-enhance-photo', methods=['POST'])
def process_enhance_photo():
    if 'image' not in request.files:
        return jsonify({'error': 'Tidak ada file gambar'}), 400
    
    file = request.files['image']
    enhancement_type = request.form.get('enhancement_type', 'sharpen')
    enhancement_level = request.form.get('enhancement_level', '3')

    if file.filename == '':
        return jsonify({'error': 'Nama file kosong'}), 400

    # --- AWAL LOGIKA PEMROSESAN (CONTOH DUMMY) ---
    # Implementasikan logika peningkatan kualitas menggunakan Pillow (ImageEnhance)
    # Contoh: ImageEnhance.Sharpness(img).enhance(float(enhancement_level))
    try:
        filename = secure_filename_custom(file.filename)
        unique_filename = f"enhanced_{uuid.uuid4().hex}_{filename}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Contoh sederhana: simpan file asli saja untuk demo
        # Anda perlu membuka gambar dengan Pillow, terapkan enhancement, lalu simpan
        img = Image.open(file.stream)
        if enhancement_type == 'sharpen':
            enhancer = ImageEnhance.Sharpness(img)
            # Level dari 1-5, perlu di-map ke faktor yang sesuai untuk Pillow
            # Misal: level 1=1.0, 2=1.5, 3=2.0, 4=2.5, 5=3.0
            factor = 1.0 + ( (float(enhancement_level) -1 ) * 0.5 ) 
            img_enhanced = enhancer.enhance(factor)
            img_enhanced.save(save_path)
        else:
            # Fitur lain (super_resolution, denoise) perlu implementasi lebih lanjut
            file.save(save_path) # Simpan asli jika enhancement type belum diimplementasi

        current_app.logger.info(f"Proses Enhance (type: {enhancement_type}, level: {enhancement_level}) untuk '{file.filename}'. Disimpan sebagai {unique_filename}")
        processed_url = f"/static/uploads/{unique_filename}"
        return jsonify({'url': processed_url, 'filename': unique_filename})
    except Exception as e:
        current_app.logger.error(f"Error dummy process_enhance_photo: {e}")
        return jsonify({'error': str(e)}), 500
    # --- AKHIR LOGIKA PEMROSESAN (CONTOH DUMMY) ---

@process_bp.route('/process-compress-photo', methods=['POST'])
def process_compress_photo():
    if 'image' not in request.files:
        return jsonify({'error': 'Tidak ada file gambar'}), 400
    
    file = request.files['image']
    quality = int(request.form.get('quality', 75)) # Kualitas 1-100 untuk JPG

    if file.filename == '':
        return jsonify({'error': 'Nama file kosong'}), 400

    # --- AWAL LOGIKA PEMROSESAN (CONTOH DUMMY) ---
    # Implementasikan logika kompresi menggunakan Pillow
    # img.save(path, quality=quality) untuk JPG
    # img.save(path, optimize=True) untuk PNG
    try:
        filename = secure_filename_custom(file.filename)
        original_name, ext = os.path.splitext(filename)
        ext = ext.lower()

        unique_filename = f"compressed_{uuid.uuid4().hex}_{original_name}{ext}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        
        img = Image.open(file.stream)
        if ext == '.jpg' or ext == '.jpeg':
            img.save(save_path, 'JPEG', quality=quality, optimize=True)
        elif ext == '.png':
            img.save(save_path, 'PNG', optimize=True)
        else:
            # Jika bukan jpg/png, simpan saja aslinya atau beri error
             return jsonify({'error': 'Hanya JPG/PNG yang bisa dikompres dengan metode ini'}), 400
        
        compressed_size_bytes = os.path.getsize(save_path)
        original_size_bytes = file.seek(0, os.SEEK_END) # Dapatkan ukuran file asli
        file.seek(0) # Kembalikan pointer file

        compression_percent = 0
        if original_size_bytes > 0:
            compression_percent = round((1 - (compressed_size_bytes / original_size_bytes)) * 100, 2)


        current_app.logger.info(f"Proses Kompresi (kualitas: {quality if ext=='.jpg' or ext=='.jpeg' else 'N/A'}) untuk '{file.filename}'. Disimpan sebagai {unique_filename}")
        processed_url = f"/static/uploads/{unique_filename}"
        return jsonify({
            'url': processed_url, 
            'filename': unique_filename,
            'size_kb': compressed_size_bytes / 1024,
            'compression_percent': compression_percent
            })
    except Exception as e:
        current_app.logger.error(f"Error dummy process_compress_photo: {e}")
        return jsonify({'error': str(e)}), 500
    


    #===============photoboth=============
    import base64 # Untuk decode data URL jika dikirim dari client

@process_bp.route('/save-photobooth-image', methods=['POST'])
def save_photobooth_image():
    data = request.json
    if not data or 'imageDataUrl' not in data:
        return jsonify({'error': 'Tidak ada data gambar'}), 400

    try:
        # imageDataUrl akan berupa: "data:image/png;base64,iVBORw0KGgoAAAANSU..."
        header, encoded = data['imageDataUrl'].split(',', 1)
        image_data = base64.b64decode(encoded)
        
        # Tentukan ekstensi dari header (meskipun kita set ke PNG di client)
        # file_extension = header.split(';')[0].split('/')[1] 
        file_extension = 'png' # Kita tahu client mengirim PNG

        filename = f"photobooth_{uuid.uuid4().hex}.{file_extension}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        with open(save_path, 'wb') as f:
            f.write(image_data)
        
        current_app.logger.info(f"Photobooth image '{filename}' saved.")
        return jsonify({
            'message': 'Foto photobooth berhasil disimpan di server.',
            'filename': filename,
            'url': f"/static/uploads/{filename}"
        }), 201 # 201 Created

    except Exception as e:
        current_app.logger.error(f"Error saving photobooth image: {e}")
        return jsonify({'error': f'Gagal menyimpan foto: {str(e)}'}), 500
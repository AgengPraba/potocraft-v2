# app/routes/process.py
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from PIL import Image, ImageEnhance # ImageEnhance untuk kecerahan jika diperlukan nanti
from rembg import remove
import uuid
import os
import io
import json
import cv2 
import numpy as np
from werkzeug.utils import secure_filename as werkzeug_secure_filename
import traceback

process_bp = Blueprint('process', __name__)

# Helper untuk memastikan nama file aman (opsional tapi bagus)
# def secure_filename_custom(filename):
#     # Implementasi sederhana, bisa diganti dengan werkzeug.utils.secure_filename jika diinginkan
#     return "".join(c for c in filename if c.isalnum() or c in ('.', '_', '-')).strip()

def secure_filename_custom(filename):
    return werkzeug_secure_filename(filename.replace(" ", "_"))

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


def _make_image_transparent_with_rembg(source_image_path_or_pil_image, original_base_filename_for_naming):
    """
    Menerima path gambar atau objek PIL Image, menghilangkan backgroundnya, 
    menyimpannya, dan mengembalikan nama file barunya.
    Selalu disimpan sebagai PNG.
    """
    try:
        if isinstance(source_image_path_or_pil_image, str): # Jika path
            if not os.path.exists(source_image_path_or_pil_image):
                raise FileNotFoundError(f"File sumber untuk transparansi tidak ditemukan: {source_image_path_or_pil_image}")
            with open(source_image_path_or_pil_image, 'rb') as f_in:
                input_bytes = f_in.read()
        elif isinstance(source_image_path_or_pil_image, Image.Image): # Jika objek PIL
            img_pil = source_image_path_or_pil_image.convert("RGB") # Rembg lebih baik dengan RGB input
            img_byte_arr = io.BytesIO()
            img_pil.save(img_byte_arr, format='PNG') # Simpan ke bytes dalam format yang bisa dibaca rembg
            input_bytes = img_byte_arr.getvalue()
        else:
            raise ValueError("Input untuk _make_image_transparent_with_rembg harus path string atau objek PIL Image.")

        output_bytes = remove(input_bytes)
        
        # Simpan hasil transparan
        base_name, _ = os.path.splitext(original_base_filename_for_naming)
        transparent_filename = f"{uuid.uuid4().hex}_{base_name}_transparent.png"
        transparent_save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], transparent_filename)
        
        with open(transparent_save_path, 'wb') as f_out:
            f_out.write(output_bytes)
        
        current_app.logger.info(f"Versi transparan '{transparent_filename}' dibuat.")
        return transparent_filename
    except Exception as e:
        current_app.logger.error(f"Gagal membuat versi transparan: {e}")
        current_app.logger.error(traceback.format_exc())
        raise # Re-raise exception untuk ditangani oleh pemanggil

@process_bp.route('/crop', methods=['POST'])
def crop_image():
    if 'cropped' not in request.files:
        return jsonify({'error': 'Tidak ada data gambar yang di-crop'}), 400

    brightness_factor = float(request.form.get('brightness', 1.0))
    cropped_file_storage = request.files['cropped']
    original_filename_from_form = request.form.get('original_filename') 

    if not (cropped_file_storage and original_filename_from_form):
        return jsonify({'error': 'File crop atau nama file asli tidak valid'}), 400

    try:
        img_pil = Image.open(cropped_file_storage.stream) # Baca dari stream
        
        # Aplikasikan kecerahan
        if brightness_factor != 1.0: # Hanya proses jika ada perubahan
            enhancer = ImageEnhance.Brightness(img_pil.convert("RGB")) # Enhance brightness pada versi RGB
            img_pil_brightened = enhancer.enhance(brightness_factor)
            # Jika gambar asli punya alpha, gabungkan kembali alpha channel ke gambar yang sudah brightened
            if 'A' in img_pil.getbands():
                alpha = img_pil.split()[-1]
                img_pil_brightened = Image.merge('RGBA', (*img_pil_brightened.split(), alpha))
            else:
                img_pil_brightened = img_pil_brightened.convert(img_pil.mode) # Kembalikan ke mode asli jika bukan RGBA
        else:
            img_pil_brightened = img_pil # Tidak ada perubahan brightness

        # Simpan gambar hasil crop + brightness
        # Gunakan original_filename_from_form untuk penamaan yang konsisten
        safe_original_filename = secure_filename_custom(original_filename_from_form)
        base_name, ext = os.path.splitext(safe_original_filename)
        # Pastikan ekstensi .png jika hasil crop (dari canvas) adalah PNG
        cropped_unique_filename = f"{uuid.uuid4().hex}_{base_name}_cb.png" 
        save_path_cropped_brightened = os.path.join(current_app.config['UPLOAD_FOLDER'], cropped_unique_filename)
        img_pil_brightened.save(save_path_cropped_brightened, 'PNG') # CropperJS biasanya menghasilkan PNG dari canvas
        current_app.logger.info(f"File crop+brightness '{cropped_unique_filename}' disimpan.")

        # Otomatis buat versi transparan dari gambar yang sudah di-crop & brightened
        transparent_version_filename = None
        try:
            # Mengirim objek PIL langsung ke helper, nama file asli untuk penamaan output transparan
            transparent_version_filename = _make_image_transparent_with_rembg(img_pil_brightened, f"{base_name}_cb{ext}")
        except Exception as e_transparent:
            current_app.logger.error(f"Gagal membuat versi transparan otomatis setelah crop: {e_transparent}")
            # Tidak mengembalikan error fatal, tapi frontend akan tahu versi transparan gagal dibuat

        return jsonify({
            'filename': cropped_unique_filename, 
            'url': f"/static/uploads/{cropped_unique_filename}",
            'transparent_filename': transparent_version_filename, # Bisa None jika gagal
            'transparent_url': f"/static/uploads/{transparent_version_filename}" if transparent_version_filename else None,
            'message': 'Crop berhasil' + ('' if transparent_version_filename else ', tetapi gagal membuat versi transparan otomatis.')
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error saat crop/brightness/auto-transparent: {e}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': f'Gagal memproses crop: {str(e)}'}), 500

@process_bp.route('/apply-color', methods=['POST'])
def apply_color_to_image():
    data = request.json
    if not data or 'transparent_filename' not in data or 'bgColor' not in data:
        return jsonify({"error": "Data tidak lengkap (transparent_filename atau bgColor tidak ada)"}), 400

    transparent_filename = secure_filename_custom(data['transparent_filename'])
    bg_color_hex = data['bgColor'].strip()

    transparent_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], transparent_filename)

    if not os.path.exists(transparent_image_path):
        return jsonify({"error": f"File transparan '{transparent_filename}' tidak ditemukan."}), 404

    try:
        img_pil_transparent = Image.open(transparent_image_path).convert("RGBA")
        output_image_pil = img_pil_transparent # Default jika tidak ada warna / warna tidak valid

        if bg_color_hex and bg_color_hex.startswith('#'):
            cleaned_hex = bg_color_hex.lstrip('#')
            if len(cleaned_hex) == 6: # #RRGGBB
                try:
                    bg_color_rgb = tuple(int(cleaned_hex[i:i+2], 16) for i in (0, 2, 4))
                    background_layer = Image.new("RGBA", img_pil_transparent.size, (*bg_color_rgb, 255))
                    output_image_pil = Image.alpha_composite(background_layer, img_pil_transparent)
                except ValueError:
                    current_app.logger.warning(f"Hex color '{bg_color_hex}' tidak valid, background tidak diubah dari transparan.")
            elif len(cleaned_hex) == 3: # #RGB
                try:
                    bg_color_rgb = tuple(int(c*2, 16) for c in cleaned_hex)
                    background_layer = Image.new("RGBA", img_pil_transparent.size, (*bg_color_rgb, 255))
                    output_image_pil = Image.alpha_composite(background_layer, img_pil_transparent)
                except ValueError:
                    current_app.logger.warning(f"Hex color (#RGB) '{bg_color_hex}' tidak valid, background tidak diubah dari transparan.")
            else: # Panjang hex tidak valid
                current_app.logger.warning(f"Panjang Hex color '{bg_color_hex}' tidak valid, background tidak diubah dari transparan.")
        else: # Tidak ada warna, biarkan transparan
            current_app.logger.info(f"bgColor tidak valid atau kosong ('{bg_color_hex}'), gambar tetap transparan.")


        base_name, _ = os.path.splitext(transparent_filename.replace('_transparent', ''))
        final_colored_filename = f"{uuid.uuid4().hex}_{base_name}_finalcolor.png"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], final_colored_filename)
        
        output_image_pil.save(save_path, 'PNG')
        current_app.logger.info(f"File dengan warna final '{final_colored_filename}' disimpan.")

        return jsonify({
            "message": "Warna background berhasil diterapkan.",
            "filename": final_colored_filename,
            "url": f"/static/uploads/{final_colored_filename}"
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error saat menerapkan warna: {e}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': f'Gagal menerapkan warna: {str(e)}'}), 500
    
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
        return jsonify({'error': 'Tidak ada file gambar yang diunggah'}), 400
    
    file = request.files['image']
    # Ambil warna background dari form data. Strip whitespace. Jika kosong, akan jadi background transparan.
    bg_color_hex = request.form.get('bgColor', '').strip() 

    if file.filename == '':
        return jsonify({'error': 'Nama file kosong'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Format file tidak diizinkan. Hanya ' + ', '.join(current_app.config['ALLOWED_EXTENSIONS']) + ' yang diizinkan.'}), 400

    try:
        input_image_bytes = file.read() # Baca file sebagai bytes
        
        # 1. Hapus background menggunakan rembg
        # Fungsi remove() dari rembg bisa menerima bytes dan mengembalikan bytes PNG RGBA (dengan background transparan)
        img_bytes_no_bg_transparent = remove(input_image_bytes) 

        # Konversi bytes hasil rembg ke objek Image Pillow untuk diproses lebih lanjut
        # Convert ke "RGBA" untuk memastikan ada channel alpha (transparansi)
        img_pil_no_bg = Image.open(io.BytesIO(img_bytes_no_bg_transparent)).convert("RGBA")

        output_image_pil = img_pil_no_bg # Defaultnya adalah gambar transparan

        # 2. Jika ada warna background yang valid, terapkan
        if bg_color_hex and bg_color_hex.startswith('#'):
            cleaned_hex = bg_color_hex.lstrip('#')
            if len(cleaned_hex) == 6: # Format #RRGGBB
                try:
                    bg_color_rgb = tuple(int(cleaned_hex[i:i+2], 16) for i in (0, 2, 4))
                    # Buat layer background dengan warna yang diminta
                    background_layer = Image.new("RGBA", img_pil_no_bg.size, (*bg_color_rgb, 255))
                    # Komposit gambar transparan di atas background berwarna
                    output_image_pil = Image.alpha_composite(background_layer, img_pil_no_bg)
                    current_app.logger.info(f"Menerapkan background warna: {bg_color_hex}")
                except ValueError:
                    current_app.logger.warning(f"Format kode warna Hex tidak valid: {bg_color_hex}. Menggunakan background transparan.")
            elif len(cleaned_hex) == 3: # Format #RGB (contoh: #F00 -> #FF0000)
                try:
                    bg_color_rgb = tuple(int(c*2, 16) for c in cleaned_hex) # Konversi #RGB ke #RRGGBB
                    background_layer = Image.new("RGBA", img_pil_no_bg.size, (*bg_color_rgb, 255))
                    output_image_pil = Image.alpha_composite(background_layer, img_pil_no_bg)
                    current_app.logger.info(f"Menerapkan background warna (dari #RGB): {bg_color_hex}")
                except ValueError:
                    current_app.logger.warning(f"Format kode warna Hex (#RGB) tidak valid: {bg_color_hex}. Menggunakan background transparan.")
            else:
                 current_app.logger.warning(f"Panjang kode warna Hex tidak valid: {bg_color_hex}. Menggunakan background transparan.")
        else:
            current_app.logger.info("Tidak ada warna background valid atau diminta transparan. Menghasilkan gambar transparan.")
            # Jika tidak ada warna yang diminta atau tidak valid, output_image_pil sudah berupa gambar transparan

        # 3. Simpan hasil akhir (selalu sebagai PNG untuk mendukung transparansi)
        original_filename_secure = secure_filename_custom(file.filename)
        base_name, _ = os.path.splitext(original_filename_secure)
        
        # Buat nama file unik untuk hasil
        unique_filename = f"removedbg_{uuid.uuid4().hex}_{base_name}.png"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        
        output_image_pil.save(save_path, 'PNG')
        
        current_app.logger.info(f"Proses Hapus BG untuk '{file.filename}'. Disimpan sebagai {unique_filename}")
        
        # URL untuk diakses dari frontend (perhatikan, ini mengarah ke folder static/uploads)
        processed_url = f"/static/uploads/{unique_filename}" 

        return jsonify({'url': processed_url, 'filename': unique_filename})

    except Exception as e:
        current_app.logger.error(f"Error saat proses remove_background: {e}")
        # Tambahkan traceback untuk debugging di server log
        import traceback
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': f'Terjadi kesalahan internal server: {str(e)}'}), 500
    
@process_bp.route('/interactive-segmentation', methods=['POST'])
def process_interactive_segmentation():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'Tidak ada file gambar'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'Nama file kosong'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Format file tidak diizinkan'}), 400

        points_str = request.form.get('points')
        if not points_str:
            return jsonify({'error': 'Tidak ada data titik seleksi'}), 400

        try:
            # points_data adalah list of dicts: [{'x': val, 'y': val, 'type': 'fg'/'bg'}, ...]
            points_data = json.loads(points_str) 
            if not isinstance(points_data, list):
                 raise ValueError("Points data bukan list")
        except (json.JSONDecodeError, ValueError) as e:
            current_app.logger.error(f"Format data titik seleksi tidak valid: {e}")
            return jsonify({'error': f'Format data titik seleksi tidak valid: {str(e)}'}), 400
        
        current_app.logger.info(f"Menerima {len(points_data)} titik dari coretan.")
        
        filestr_bytes = file.read() # Baca sekali untuk digunakan beberapa kali jika perlu
        npimg = np.frombuffer(filestr_bytes, np.uint8)
        img_cv = cv2.imdecode(npimg, cv2.IMREAD_COLOR)

        if img_cv is None:
            return jsonify({'error': 'Gagal membaca format gambar'}), 400

        mask = np.zeros(img_cv.shape[:2], np.uint8)
        rect = (0,0,1,1) # Default rect minimal jika tidak ada titik valid

        if points_data:
            # Filter hanya titik yang memiliki x dan y numerik
            valid_points = [p for p in points_data if isinstance(p, dict) and 
                            isinstance(p.get('x'), (int, float)) and 
                            isinstance(p.get('y'), (int, float))]

            if not valid_points:
                current_app.logger.warning("Tidak ada titik dengan koordinat valid, mencoba rembg.")
                # (Logika fallback ke rembg seperti sebelumnya)
                try:
                    output_bytes_rembg = remove(filestr_bytes)
                    # ... (sisa logika fallback rembg dan return)
                    img_pil_rembg = Image.open(io.BytesIO(output_bytes_rembg)).convert("RGBA")
                    original_filename_secure = secure_filename_custom(file.filename)
                    base_name, _ = os.path.splitext(original_filename_secure)
                    unique_filename = f"rembg_fallback_{uuid.uuid4().hex}_{base_name}.png"
                    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                    img_pil_rembg.save(save_path, 'PNG')
                    return jsonify({'url': f"/static/uploads/{unique_filename}", 'filename': unique_filename})
                except Exception as e_rembg:
                    current_app.logger.error(f"Fallback ke rembg gagal: {e_rembg}")
                    return jsonify({'error': 'Tidak ada titik seleksi valid & fallback rembg gagal.'}), 500


            all_x = [p['x'] for p in valid_points]
            all_y = [p['y'] for p in valid_points]
            
            rect_x = int(min(all_x))
            rect_y = int(min(all_y))
            # Lebar dan tinggi harus setidaknya 1 piksel
            rect_w = int(max(1, max(all_x) - rect_x)) 
            rect_h = int(max(1, max(all_y) - rect_y))
            
            # Penyesuaian rect agar tidak keluar batas gambar
            rect_x = max(0, rect_x); rect_y = max(0, rect_y)
            if rect_x + rect_w >= img_cv.shape[1]: rect_w = img_cv.shape[1] - rect_x - 1
            if rect_y + rect_h >= img_cv.shape[0]: rect_h = img_cv.shape[0] - rect_y - 1
            rect_w = max(1, rect_w); rect_h = max(1, rect_h) # Pastikan > 0
                
            rect = (rect_x, rect_y, rect_w, rect_h)
            current_app.logger.info(f"Bounding box untuk GrabCut dari coretan: {rect}")

            # Tandai mask berdasarkan titik-titik dari coretan
            # Radius/ketebalan coretan pada mask bisa disesuaikan
            scribble_radius = 5 # Radius untuk setiap titik dari coretan
            for p in valid_points:
                px, py = int(p['x']), int(p['y'])
                point_type = p.get('type', 'fg') # Default ke fg jika tipe tidak ada

                if 0 <= py < img_cv.shape[0] and 0 <= px < img_cv.shape[1]:
                    if point_type == 'fg':
                        cv2.circle(mask, (px,py), scribble_radius, cv2.GC_FGD, -1) 
                    elif point_type == 'bg':
                        cv2.circle(mask, (px,py), scribble_radius, cv2.GC_BGD, -1)
            
            # Jika tidak ada titik FG eksplisit, tandai seluruh area rect sebagai probable FG
            has_fg_points = any(p.get('type') == 'fg' for p in valid_points)
            if not has_fg_points and (rect_w > 0 and rect_h > 0):
                mask[rect_y:rect_y+rect_h, rect_x:rect_x+rect_w] = cv2.GC_PR_FGD
        else: # Tidak ada points_data sama sekali, fallback ke rembg
            current_app.logger.info("Tidak ada titik seleksi sama sekali, mencoba rembg.")
            # (Logika fallback ke rembg seperti di atas)
            output_bytes_rembg = remove(filestr_bytes)
            img_pil_rembg = Image.open(io.BytesIO(output_bytes_rembg)).convert("RGBA")
            original_filename_secure = secure_filename_custom(file.filename)
            base_name, _ = os.path.splitext(original_filename_secure)
            unique_filename = f"rembg_fallback_nopoints_{uuid.uuid4().hex}_{base_name}.png"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            img_pil_rembg.save(save_path, 'PNG')
            return jsonify({'url': f"/static/uploads/{unique_filename}", 'filename': unique_filename})


        bgdModel = np.zeros((1,65), np.float64)
        fgdModel = np.zeros((1,65), np.float64)
        
        current_app.logger.info("Menjalankan GrabCut dengan mask dari coretan...")
        if rect[2] <= 0 or rect[3] <= 0:
             current_app.logger.error(f"Bounding box tidak valid untuk GrabCut: {rect}.")
             raise ValueError("Bounding box tidak valid untuk GrabCut.")

        cv2.grabCut(img_cv, mask, rect, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_MASK) # Iterasi bisa ditambah
        
        mask2 = np.where((mask==cv2.GC_PR_FGD) | (mask==cv2.GC_FGD), 1, 0).astype('uint8')
        img_rgba_cv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGBA)
        img_rgba_cv[:, :, 3] = mask2 * 255 # Terapkan alpha mask
        output_image_pil = Image.fromarray(cv2.cvtColor(img_rgba_cv, cv2.COLOR_BGRA2RGBA))

        original_filename_secure = secure_filename_custom(file.filename)
        base_name, _ = os.path.splitext(original_filename_secure)
        unique_filename = f"interactive_seg_{uuid.uuid4().hex}_{base_name}.png"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        output_image_pil.save(save_path, 'PNG')
        
        current_app.logger.info(f"Proses Seleksi Interaktif (GrabCut) untuk '{file.filename}'. Disimpan sebagai {unique_filename}")
        return jsonify({'url': f"/static/uploads/{unique_filename}", 'filename': unique_filename})

    except ValueError as ve: 
        current_app.logger.error(f"ValueError saat proses seleksi interaktif: {ve}. Mencoba rembg sebagai fallback.")
        try:
            file.seek(0) 
            input_image_bytes_for_rembg = file.read()
            output_bytes_rembg = remove(input_image_bytes_for_rembg)
            # ... (sisa logika fallback rembg dan return)
            img_pil_rembg = Image.open(io.BytesIO(output_bytes_rembg)).convert("RGBA")
            original_filename_secure = secure_filename_custom(file.filename)
            base_name, _ = os.path.splitext(original_filename_secure)
            unique_filename = f"rembg_fallback_verr_{uuid.uuid4().hex}_{base_name}.png"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            img_pil_rembg.save(save_path, 'PNG')
            return jsonify({'url': f"/static/uploads/{unique_filename}", 'filename': unique_filename})
        except Exception as e_rembg_fallback:
            # ... (error handling fallback)
            return jsonify({'error': f'Gagal memproses seleksi dan fallback: {str(e_rembg_fallback)}'}), 500
    except Exception as e: 
        current_app.logger.error(f"Error tidak terduga: {e}")   
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': f'Terjadi kesalahan internal server: {str(e)}'}), 500


#============================ fitur peningkatan kualitas image ============================
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


#============================ fitur kompresi image ============================
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


@process_bp.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
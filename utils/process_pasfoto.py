import cv2
import numpy as np
import os

def process_pasfoto(input_path, output_path, background_color="biru", target_size=(354, 472)):
    """
    input_path: path gambar asli
    output_path: path hasil pas foto
    background_color: 'merah', 'biru', atau 'putih'
    target_size: ukuran output (default: 3x4 dalam px, asumsi 300 dpi)

    return: True jika berhasil
    """
    # Baca gambar
    img = cv2.imread(input_path)
    if img is None:
        return False

    # Deteksi wajah
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    if len(faces) == 0:
        return False  # tidak ada wajah

    # Ambil wajah pertama
    
    (x, y, w, h) = faces[0]

    # Tentukan bounding box proporsional (misal 1.5x tinggi wajah)
    center_x = x + w // 2
    center_y = y + h // 2
    scale = 2.0
    new_w = int(w * scale)
    new_h = int(h * scale)
    x1 = max(center_x - new_w // 2, 0)
    y1 = max(center_y - new_h // 2, 0)
    x2 = min(center_x + new_w // 2, img.shape[1])
    y2 = min(center_y + new_h // 2, img.shape[0])

    cropped = img[y1:y2, x1:x2]

    # Resize ke ukuran target
    resized = cv2.resize(cropped, target_size)

    # Buat latar belakang sesuai warna
    if background_color == "biru":
        bg = [255, 0, 0]  # BGR
    elif background_color == "merah":
        bg = [0, 0, 255]
    elif background_color == "putih":
        bg = [255, 255, 255]
    else:
        bg = [255, 255, 255]

    bg_img = np.full_like(resized, bg)

    # Deteksi segmen wajah dengan skin color untuk masking kasar
    hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
    lower = np.array([0, 40, 40], dtype=np.uint8)
    upper = np.array([25, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    mask = cv2.bitwise_not(mask)

    # Refine mask sedikit
    mask = cv2.GaussianBlur(mask, (7,7), 0)
    mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)[1]

    # Ganti background
    fg = cv2.bitwise_and(resized, resized, mask=mask)
    inv_mask = cv2.bitwise_not(mask)
    bg_applied = cv2.bitwise_and(bg_img, bg_img, mask=inv_mask)
    result = cv2.add(fg, bg_applied)

    # Simpan hasil
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, result)
    return True

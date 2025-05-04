import cv2
import numpy as np
from PIL import Image

def remove_background(image_path, background_color='putih'):
    # Baca gambar
    image = cv2.imread(image_path)
    # Konversi ke grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Gunakan deteksi wajah atau teknik lain untuk menentukan objek (masking)
    # Untuk penyederhanaan, kita asumsikan sudah ada mask atau background dihapus menggunakan metode GrabCut
    mask = np.zeros(image.shape[:2], np.uint8)
    bg_model = np.zeros((1, 65), np.float64)
    fg_model = np.zeros((1, 65), np.float64)
    rect = (10, 10, image.shape[1]-10, image.shape[0]-10)
    
    # Panggil GrabCut
    cv2.grabCut(image, mask, rect, bg_model, fg_model, 5, cv2.GC_INIT_WITH_RECT)
    
    # Hapus background, pilih hasil foreground
    mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
    result = image * mask2[:, :, np.newaxis]
    
    # Pilih warna latar belakang
    warna_map = {
        'merah': (0, 0, 255),  # Red
        'biru': (255, 0, 0),   # Blue
        'putih': (255, 255, 255)  # White
    }
    latar = warna_map.get(background_color, (255, 255, 255))  # Default putih

    # Ganti latar belakang dengan warna yang dipilih
    background = np.full_like(image, latar, dtype=np.uint8)
    result = np.where(result == 0, background, result)
    
    return result

def save_image(image, output_path):
    cv2.imwrite(output_path, image)

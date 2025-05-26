import os
from flask import Flask
from .routes.main import main_bp  # Menggunakan relative import jika file ini di dalam package 'app'
from .routes.process import process_bp # Menggunakan relative import

def create_app():
    app = Flask(__name__,
                # template_folder dan static_folder sudah benar jika __init__.py ada di dalam 'app'
                # dan 'templates' serta 'static' ada di level yang sama dengan 'app' (../)
                template_folder='../templates', 
                static_folder='../static')

    # 1. Konfigurasi UPLOAD_FOLDER dengan path absolut yang robust
    # app.static_folder akan menjadi path absolut ke folder statis Anda (misalnya, C:/static)
    # setelah inisialisasi Flask.
    upload_folder_path = os.path.join(app.static_folder, 'uploads')
    app.config['UPLOAD_FOLDER'] = upload_folder_path
    
    # 2. Pastikan direktori UPLOAD_FOLDER ada saat aplikasi dimulai
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        app.logger.info(f"Upload folder is set to: {app.config['UPLOAD_FOLDER']}")
    except OSError as e:
        app.logger.error(f"Error creating upload folder {app.config['UPLOAD_FOLDER']}: {e}")


    # 3. Register blueprints
    app.register_blueprint(main_bp) 
    # Tambahkan url_prefix untuk process_bp agar konsisten dengan url_for('process.nama_fungsi')
    # yang akan menghasilkan URL seperti /process/upload
    app.register_blueprint(process_bp, url_prefix='/process')

    # Contoh: Logging untuk memastikan path sudah benar (opsional, bagus untuk debugging)
    app.logger.info(f"App root path: {app.root_path}")
    app.logger.info(f"Static folder: {app.static_folder}")
    app.logger.info(f"Template folder: {app.template_folder}") # Ini adalah nama yang diberikan, bukan path absolutnya

    return app
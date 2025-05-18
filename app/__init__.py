from flask import Flask
from app.routes.main import main_bp
from app.routes.process import process_bp

def create_app():
    app = Flask(__name__, 
                template_folder='../templates',  # Sesuaikan dengan lokasi folder templates Anda
                static_folder='../static')
    app.config['UPLOAD_FOLDER'] = '../static/uploads'

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(process_bp)

    return app

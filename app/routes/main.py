from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.jinja')

@main_bp.route('/pasfoto')
def pasfoto():
    return render_template('pasfoto2.jinja')

@main_bp.route('/hapus-background')
def hapus_background():
    return render_template('hapus_background_interactive.jinja')

@main_bp.route('/tingkatkan-foto')
def tingkatkan_foto():
    return render_template('tingkatkan_foto.jinja')

@main_bp.route('/kompresi-foto')
def kompresi_foto():
    return render_template('kompresi_foto.jinja')

@main_bp.route('/photobooth')
def photobooth_page():
    return render_template('photobooth.jinja', title="Photobooth - Potocraft")
